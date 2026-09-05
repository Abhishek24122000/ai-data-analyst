"""
Deterministic dataset profiler.

Runs once per uploaded dataset (not per question) and produces a compact
JSON summary that is (a) shown in the "Dataset" panel on the frontend and
(b) fed into the LLM prompt as schema context -- this is the mechanism that
keeps raw rows out of the model's context window: the model only ever sees
this profile plus small query results, never the full dataframe.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

MAX_CATEGORY_VALUES = 8


def _is_probably_date(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if series.dtype == object:
        sample = series.dropna().head(20)
        if sample.empty:
            return False
        try:
            pd.to_datetime(sample, errors="raise")
            return True
        except (ValueError, TypeError):
            return False
    return False


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    n_rows, n_cols = df.shape
    duplicate_rows = int(df.duplicated().sum())

    columns: list[dict[str, Any]] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    date_cols: list[str] = []

    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        col_info: dict[str, Any] = {
            "name": col,
            "dtype": str(series.dtype),
            "missing_count": missing,
            "missing_pct": round(missing / n_rows * 100, 2) if n_rows else 0.0,
            "n_unique": int(series.nunique(dropna=True)),
        }

        if _is_probably_date(series):
            date_cols.append(col)
            col_info["semantic_type"] = "date"
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().any():
                col_info["min"] = str(parsed.min().date())
                col_info["max"] = str(parsed.max().date())
        elif pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col)
            col_info["semantic_type"] = "numeric"
            desc = series.describe()
            col_info["stats"] = {
                "min": round(float(desc.get("min", 0)), 2),
                "max": round(float(desc.get("max", 0)), 2),
                "mean": round(float(desc.get("mean", 0)), 2),
                "std": round(float(desc.get("std", 0)), 2),
                "p25": round(float(desc.get("25%", 0)), 2),
                "p50": round(float(desc.get("50%", 0)), 2),
                "p75": round(float(desc.get("75%", 0)), 2),
            }
        else:
            categorical_cols.append(col)
            col_info["semantic_type"] = "categorical"
            top = series.value_counts(dropna=True).head(MAX_CATEGORY_VALUES)
            col_info["top_values"] = [
                {"value": str(k), "count": int(v)} for k, v in top.items()
            ]

        columns.append(col_info)

    correlations: dict[str, dict[str, float]] = {}
    if len(numeric_cols) >= 2:
        corr_matrix = df[numeric_cols].corr(numeric_only=True).round(3)
        for a in numeric_cols:
            correlations[a] = {
                b: float(corr_matrix.loc[a, b])
                for b in numeric_cols
                if a != b and not np.isnan(corr_matrix.loc[a, b])
            }

    # Lightweight heuristics used both by the fallback NLU and by the
    # suggested-questions generator to point at "the" revenue/date column
    # without hardcoding column names.
    likely_metric_cols = [
        c for c in numeric_cols
        if any(k in c.lower() for k in ["revenue", "sales", "amount", "price", "total", "profit"])
    ] or numeric_cols[:1]
    likely_date_col = date_cols[0] if date_cols else None

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_rows / n_rows * 100, 2) if n_rows else 0.0,
        "missing_cells": int(df.isna().sum().sum()),
        "columns": columns,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "date_columns": date_cols,
        "correlations": correlations,
        "likely_metric_columns": likely_metric_cols,
        "likely_date_column": likely_date_col,
    }


def schema_context_for_llm(profile: dict[str, Any], table_name: str = "data") -> str:
    """Compact textual schema description injected into LLM prompts."""
    lines = [f"Table name: {table_name}", f"Rows: {profile['n_rows']:,}", "Columns:"]
    for col in profile["columns"]:
        extra = ""
        if col["semantic_type"] == "numeric":
            s = col["stats"]
            extra = f" (numeric, range {s['min']}..{s['max']}, mean {s['mean']})"
        elif col["semantic_type"] == "date":
            extra = f" (date, {col.get('min', '?')} to {col.get('max', '?')})"
        elif col["semantic_type"] == "categorical":
            vals = ", ".join(v["value"] for v in col.get("top_values", [])[:5])
            extra = f" (categorical, top values: {vals})"
        lines.append(f"  - {col['name']}: {col['dtype']}{extra}")
    return "\n".join(lines)
