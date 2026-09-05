"""
Central configuration for the AI Data Analyst backend.

All runtime knobs (LLM provider, model, storage paths, upload limits, CORS)
are controlled via environment variables so the same code runs unchanged
locally, in Docker, and on Render.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM provider ---------------------------------------------------
    # "groq" (free, OpenAI-compatible), "openai", "anthropic", or "none"
    # ("none" forces the deterministic fallback NLU so the app still runs
    # with zero API keys configured -- see agents/fallback_nlu.py).
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")

    # --- Storage ----------------------------------------------------------
    storage_dir: Path = Path(os.getenv("STORAGE_DIR", "./storage"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "50"))

    # --- Agent behaviour ----------------------------------------------------
    max_sql_retries: int = int(os.getenv("MAX_SQL_RETRIES", "2"))
    max_history_turns: int = int(os.getenv("MAX_HISTORY_TURNS", "6"))
    max_result_rows: int = int(os.getenv("MAX_RESULT_ROWS", "500"))

    # --- CORS ---------------------------------------------------------------
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_api_key)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "datasets").mkdir(parents=True, exist_ok=True)
    return settings
