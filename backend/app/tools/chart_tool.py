"""
Deterministic chart-type selection based on the *shape* of the query
result (row count, column count, and dtypes) -- not chosen by the LLM.
This avoids the failure mode where a model confidently asks for a chart
type that doesn't fit the data it just returned.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def select_chart(df: pd.DataFrame, hint: str | None = None) -> dict[str, Any]:
    if df.empty:
        return {"type": "empty"}

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    non_numeric_cols = [c for c in df.columns if c not in numeric_cols]
    date_like_cols = [
        c for c in non_numeric_cols
        if "date" in c.lower() or "month" in c.lower() or "year" in c.lower() or "week" in c.lower()
    ]

    # Single value -> stat tile, regardless of what the model hinted.
    if df.shape == (1, 1):
        return {"type": "stat", "value_key": df.columns[0]}

    # One row, multiple numeric columns (e.g. two-month comparison row) -> stat row
    if len(df) <= 2 and date_like_cols and numeric_cols:
        return {
            "type": "bar",
            "x_key": date_like_cols[0],
            "y_key": numeric_cols[0],
            "data": _records(df),
        }

    if date_like_cols and numeric_cols:
        return {
            "type": "line",
            "x_key": date_like_cols[0],
            "y_key": numeric_cols[0],
            "data": _records(df),
        }

    if non_numeric_cols and numeric_cols and len(df) <= 30:
        return {
            "type": "bar",
            "x_key": non_numeric_cols[0],
            "y_key": numeric_cols[0],
            "data": _records(df),
        }

    if len(numeric_cols) >= 2 and len(df) > 5:
        return {
            "type": "scatter",
            "x_key": numeric_cols[0],
            "y_key": numeric_cols[1],
            "data": _records(df),
        }

    return {"type": "table", "columns": list(df.columns), "data": _records(df)}


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].astype(str)
    safe = safe.where(pd.notnull(safe), None)
    return safe.to_dict(orient="records")
