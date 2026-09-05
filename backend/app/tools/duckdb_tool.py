"""
Executes guarded SQL against a dataset's Parquet file via DuckDB.

Each call opens a fresh in-memory DuckDB connection and registers the
dataset's Parquet file as a view named `data`. This keeps the backend
stateless/horizontally-scalable (no long-lived per-session DB connections)
while still getting DuckDB's fast columnar execution on-demand.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from app.security.sql_guard import SQLGuardError, validate_and_prepare


class QueryExecutionError(RuntimeError):
    """Raised when a *guard-approved* query still fails at execution time
    (bad column name, type mismatch, etc.) -- distinct from SQLGuardError
    so the orchestrator can decide whether a retry makes sense."""


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: float
    dataframe: pd.DataFrame


def run_query(parquet_path: Path, sql: str, max_rows: int = 500) -> QueryResult:
    try:
        guard_result = validate_and_prepare(sql, allowed_tables=["data"], default_limit=max_rows)
    except SQLGuardError:
        raise  # let the caller (orchestrator) decide on retry vs. surfacing

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"CREATE VIEW data AS SELECT * FROM read_parquet('{str(parquet_path).replace(chr(39), chr(39) + chr(39))}')"
        )
        start = time.perf_counter()
        try:
            df = con.execute(guard_result.safe_sql).fetchdf()
        except Exception as exc:  # noqa: BLE001
            raise QueryExecutionError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000
    finally:
        con.close()

    if len(df) > max_rows:
        df = df.head(max_rows)

    # Make the frame JSON-safe (Timestamps, NaN, numpy scalars).
    json_df = df.copy()
    for col in json_df.columns:
        if pd.api.types.is_datetime64_any_dtype(json_df[col]):
            json_df[col] = json_df[col].astype(str)
    json_df = json_df.where(pd.notnull(json_df), None)

    return QueryResult(
        sql=guard_result.safe_sql,
        columns=list(df.columns),
        rows=json_df.to_dict(orient="records"),
        row_count=len(df),
        execution_ms=round(elapsed_ms, 2),
        dataframe=df,
    )
