"""
Provider-agnostic LLM client.

Supports three backends behind one interface:
  - "groq"     : free tier, OpenAI-compatible endpoint (default -- zero cost)
  - "openai"   : official OpenAI API
  - "anthropic": Claude via the Anthropic SDK
  - "none"     : no key configured -> callers should use the deterministic
                 fallback NLU (agents/fallback_nlu.py) instead of calling
                 this client at all.

Swapping providers is a single env var (LLM_PROVIDER) plus an API key --
no code changes, which is the point: the agent layer above never imports
a provider SDK directly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.config import get_settings


class LLMError(RuntimeError):
    pass


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        if self.settings.llm_enabled:
            self._init_client()

    def _init_client(self) -> None:
        provider = self.settings.llm_provider
        if provider in ("groq", "openai"):
            from openai import OpenAI

            base_url = self.settings.llm_base_url if provider == "groq" else None
            self._client = OpenAI(api_key=self.settings.llm_api_key, base_url=base_url)
        elif provider == "anthropic":
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.settings.llm_api_key)
        else:
            raise LLMError(f"Unknown LLM provider: {provider}")

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def chat(self, messages: list[ChatMessage], temperature: float = 0.1, max_tokens: int = 1024) -> str:
        if not self.enabled:
            raise LLMError("No LLM configured (LLM_PROVIDER=none or missing API key).")

        provider = self.settings.llm_provider
        if provider in ("groq", "openai"):
            resp = self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""

        if provider == "anthropic":
            system = "\n".join(m.content for m in messages if m.role == "system")
            turns = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
            resp = self._client.messages.create(
                model=self.settings.llm_model,
                system=system or None,
                messages=turns,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return "".join(block.text for block in resp.content if hasattr(block, "text"))

        raise LLMError(f"Unknown LLM provider: {provider}")

    def chat_json(self, messages: list[ChatMessage], temperature: float = 0.1, max_tokens: int = 1024) -> dict:
        """Chat and parse a JSON object out of the response, tolerating
        markdown code fences and minor formatting noise from the model."""
        raw = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return extract_json(raw)


def extract_json(raw: str) -> dict:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {exc}\nRaw: {raw[:300]}") from exc
