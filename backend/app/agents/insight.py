"""
Insight generation.

The critical design decision here (and the answer to "how do you know the
LLM didn't hallucinate the number?" in an interview): the LLM NEVER
computes the headline number. Python computes every fact -- the value,
the prior-period comparison, the percent change -- straight from the
DuckDB result. The LLM's only job is to phrase those pre-computed facts
in a sentence. If no LLM is configured, a template does the phrasing
instead and the app degrades gracefully rather than breaking.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.llm_client import ChatMessage, LLMClient
from app.agents.prompts import INSIGHT_SYSTEM_PROMPT, INSIGHT_USER_TEMPLATE


def _fmt_num(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"{x/1_000_000:,.2f}M"
    if abs(x) >= 1_000:
        return f"{x:,.0f}"
    return f"{x:,.2f}"


def compute_facts(df: pd.DataFrame) -> dict[str, Any]:
    """Pure-Python fact extraction -- no LLM involved."""
    facts: dict[str, Any] = {"row_count": len(df)}
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    if df.shape == (1, 1):
        col = df.columns[0]
        facts["headline_label"] = col
        facts["headline_value"] = float(df.iloc[0, 0]) if pd.notna(df.iloc[0, 0]) else None
        return facts

    if numeric_cols and len(df) >= 1:
        main_metric = numeric_cols[0]
        facts["headline_label"] = main_metric
        facts["headline_value"] = float(df[main_metric].iloc[0])

        if len(df) >= 2:
            current = float(df[main_metric].iloc[0])
            previous = float(df[main_metric].iloc[1])
            if previous != 0:
                pct_change = (current - previous) / abs(previous) * 100
                facts["comparison_value"] = previous
                facts["pct_change"] = round(pct_change, 1)
            facts["top_row"] = df.iloc[0].to_dict()
            facts["second_row"] = df.iloc[1].to_dict()

        if len(df) > 2:
            facts["top_rows"] = df.head(5).to_dict(orient="records")

    return facts


def facts_to_text(facts: dict[str, Any]) -> str:
    lines = []
    if "headline_value" in facts and facts["headline_value"] is not None:
        lines.append(f"{facts.get('headline_label', 'value')} = {_fmt_num(facts['headline_value'])}")
    if "pct_change" in facts:
        direction = "increase" if facts["pct_change"] >= 0 else "decrease"
        lines.append(
            f"vs. previous period ({_fmt_num(facts['comparison_value'])}): "
            f"{abs(facts['pct_change'])}% {direction}"
        )
    if "top_rows" in facts:
        lines.append(f"Top rows: {facts['top_rows']}")
    lines.append(f"Result row count: {facts['row_count']}")
    return "\n".join(lines)


def generate_insight(question: str, df: pd.DataFrame, llm: LLMClient) -> tuple[str, dict[str, Any]]:
    facts = compute_facts(df)
    facts_text = facts_to_text(facts)

    if llm.enabled:
        try:
            text = llm.chat(
                [
                    ChatMessage("system", INSIGHT_SYSTEM_PROMPT),
                    ChatMessage("user", INSIGHT_USER_TEMPLATE.format(question=question, facts=facts_text)),
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return text.strip(), facts
        except Exception:  # noqa: BLE001 -- fall through to template on any LLM failure
            pass

    # Template fallback (also used when no LLM is configured).
    if "headline_value" in facts and facts["headline_value"] is not None:
        sentence = f"{facts.get('headline_label', 'Result')}: {_fmt_num(facts['headline_value'])}."
        if "pct_change" in facts:
            direction = "up" if facts["pct_change"] >= 0 else "down"
            sentence += f" That's {direction} {abs(facts['pct_change'])}% versus the prior period ({_fmt_num(facts['comparison_value'])})."
        return sentence, facts

    return f"Query returned {facts['row_count']} row(s). See the table/chart below for details.", facts
