"""Suggested-questions generator (Agent 2 in the architecture doc).

Runs once right after upload. Tries the LLM first (grounded in the actual
column names via the schema string); falls back to a heuristic generator
built from the profile so suggestions still appear with zero API keys.
"""
from __future__ import annotations

from app.agents.llm_client import ChatMessage, LLMClient
from app.agents.prompts import SUGGESTIONS_SYSTEM_PROMPT, SUGGESTIONS_USER_TEMPLATE
from app.data.profiler import schema_context_for_llm


def _quality_notes(profile: dict) -> str:
    notes = []
    if profile["duplicate_rows"]:
        notes.append(f"{profile['duplicate_rows']} duplicate rows ({profile['duplicate_pct']}%)")
    missing_cols = [c["name"] for c in profile["columns"] if c["missing_count"] > 0]
    if missing_cols:
        notes.append(f"missing values in: {', '.join(missing_cols)}")
    return "; ".join(notes) if notes else "no major data quality issues detected"


def _heuristic_suggestions(profile: dict) -> list[dict[str, str]]:
    metric = profile["likely_metric_columns"][0] if profile["likely_metric_columns"] else None
    date_col = profile["likely_date_column"]
    cats = profile["categorical_columns"]
    out: list[dict[str, str]] = []

    if metric:
        out.append({"category": "Metrics", "question": f"What is the total {metric.replace('_', ' ')}?"})
        out.append({"category": "Metrics", "question": f"What is the average {metric.replace('_', ' ')}?"})
    if metric and date_col:
        out.append({"category": "Trend", "question": f"Show me the monthly trend of {metric.replace('_', ' ')}."})
        out.append({"category": "Trend", "question": f"What was {metric.replace('_', ' ')} last month vs the month before?"})
    if metric and cats:
        cat = cats[0]
        out.append({"category": "Breakdown", "question": f"Which {cat.replace('_', ' ')} has the highest {metric.replace('_', ' ')}?"})
        out.append({"category": "Breakdown", "question": f"Show {metric.replace('_', ' ')} by {cat.replace('_', ' ')}."})
    if profile["duplicate_rows"] or any(c["missing_count"] > 0 for c in profile["columns"]):
        out.append({"category": "Data quality", "question": "Which columns have missing values?"})
        out.append({"category": "Data quality", "question": "How many duplicate rows are in this dataset?"})
    out.append({"category": "Overview", "question": "How many rows are in this dataset?"})
    return out[:8]


def generate_suggestions(profile: dict, llm: LLMClient) -> list[dict[str, str]]:
    if llm.enabled:
        try:
            result = llm.chat_json(
                [
                    ChatMessage("system", SUGGESTIONS_SYSTEM_PROMPT),
                    ChatMessage(
                        "user",
                        SUGGESTIONS_USER_TEMPLATE.format(
                            schema=schema_context_for_llm(profile),
                            quality_notes=_quality_notes(profile),
                        ),
                    ),
                ],
                temperature=0.4,
                max_tokens=600,
            )
            suggestions = result.get("suggestions", [])
            if suggestions:
                return suggestions[:8]
        except Exception:  # noqa: BLE001
            pass
    return _heuristic_suggestions(profile)
