"""
Deterministic, zero-LLM fallback question understanding.

Used automatically when LLM_PROVIDER=none or no API key is configured, so
the whole pipeline (profiler -> SQL -> guard -> DuckDB -> chart -> insight)
is demoable and testable with zero external dependencies. It only handles
a handful of common analytical patterns (totals, averages, group-by
rankings, monthly trends, row counts) via regex/keyword matching against
the dataset's actual column names -- it does not try to be a general NLU
system. When it can't confidently match a pattern it returns a safe
"show me the data" query and flags `low_confidence=True` so the frontend
can nudge the user to configure a real LLM key for open-ended questions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FallbackPlan:
    sql: str
    chart_hint: str
    reasoning: str
    low_confidence: bool = False
    matched_pattern: str = field(default="")


def _best_metric_column(question: str, likely_metrics: list[str], numeric_cols: list[str]) -> str | None:
    q = question.lower()
    for col in numeric_cols:
        if col.lower() in q or col.lower().replace("_", " ") in q:
            return col
    return likely_metrics[0] if likely_metrics else (numeric_cols[0] if numeric_cols else None)


def _best_category_column(question: str, categorical_cols: list[str]) -> str | None:
    q = question.lower()
    for col in categorical_cols:
        if col.lower() in q or col.lower().replace("_", " ") in q:
            return col
    # Heuristic: "region", "segment", "category", "channel", "product" style words
    for col in categorical_cols:
        for hint in ("region", "segment", "categor", "channel", "product", "country", "city"):
            if hint in col.lower():
                return col
    return categorical_cols[0] if categorical_cols else None


def plan_query(question: str, profile: dict) -> FallbackPlan:
    q = question.lower()
    numeric_cols = profile.get("numeric_columns", [])
    categorical_cols = profile.get("categorical_columns", [])
    date_col = profile.get("likely_date_column")
    likely_metrics = profile.get("likely_metric_columns", [])
    metric = _best_metric_column(question, likely_metrics, numeric_cols)

    # 1) Row count / how many records
    if re.search(r"\bhow many (rows|records|orders|entries)\b", q) or q.strip() in {"count", "row count"}:
        return FallbackPlan(
            sql="SELECT COUNT(*) AS row_count FROM data",
            chart_hint="stat",
            reasoning="Matched row-count pattern.",
            matched_pattern="row_count",
        )

    # 2) Trend / over time / by month
    if date_col and any(k in q for k in ["trend", "over time", "by month", "monthly", "each month"]):
        if metric:
            sql = (
                f"SELECT date_trunc('month', {date_col}) AS month, "
                f"SUM({metric}) AS total_{metric} FROM data "
                f"GROUP BY 1 ORDER BY 1"
            )
            return FallbackPlan(sql=sql, chart_hint="line", reasoning="Matched monthly trend pattern.",
                                 matched_pattern="trend")

    # 3) "last month" / "this month" style single-period totals
    if date_col and metric and any(k in q for k in ["last month", "this month", "previous month"]):
        sql = (
            f"WITH monthly AS (SELECT date_trunc('month', {date_col}) AS month, "
            f"SUM({metric}) AS total_{metric} FROM data GROUP BY 1 ORDER BY 1) "
            f"SELECT * FROM monthly ORDER BY month DESC LIMIT 2"
        )
        return FallbackPlan(sql=sql, chart_hint="bar", reasoning="Matched last-month comparison pattern.",
                             matched_pattern="last_month")

    # 4) Ranking: "which <category> ... highest/most/top"
    if any(k in q for k in ["highest", "most", "top", "best", "largest"]):
        cat = _best_category_column(question, categorical_cols)
        if cat and metric:
            n_match = re.search(r"\btop\s+(\d+)\b", q)
            limit = int(n_match.group(1)) if n_match else 10
            sql = (
                f"SELECT {cat}, SUM({metric}) AS total_{metric} FROM data "
                f"GROUP BY {cat} ORDER BY total_{metric} DESC LIMIT {limit}"
            )
            return FallbackPlan(sql=sql, chart_hint="bar", reasoning="Matched ranking pattern.",
                                 matched_pattern="ranking")

    # 5) Breakdown: "<metric> by <category>"
    if " by " in q:
        cat = _best_category_column(question, categorical_cols)
        if cat and metric:
            sql = (
                f"SELECT {cat}, SUM({metric}) AS total_{metric} FROM data "
                f"GROUP BY {cat} ORDER BY total_{metric} DESC"
            )
            return FallbackPlan(sql=sql, chart_hint="bar", reasoning="Matched breakdown-by pattern.",
                                 matched_pattern="breakdown")

    # 6) Average
    if any(k in q for k in ["average", "avg", "mean"]) and metric:
        sql = f"SELECT AVG({metric}) AS average_{metric} FROM data"
        return FallbackPlan(sql=sql, chart_hint="stat", reasoning="Matched average pattern.",
                             matched_pattern="average")

    # 7) Total / sum (default numeric question)
    if metric and any(k in q for k in ["total", "sum", "revenue", "how much"]):
        sql = f"SELECT SUM({metric}) AS total_{metric} FROM data"
        return FallbackPlan(sql=sql, chart_hint="stat", reasoning="Matched total/sum pattern.",
                             matched_pattern="total")

    # 8) Fallback: just show a sample so the user sees something useful.
    return FallbackPlan(
        sql="SELECT * FROM data LIMIT 20",
        chart_hint="table",
        reasoning="No confident pattern match; showing a sample of the data.",
        low_confidence=True,
        matched_pattern="sample_fallback",
    )
