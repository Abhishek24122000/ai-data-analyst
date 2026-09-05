"""
Unit tests covering the deterministic parts of the pipeline: profiler,
SQL safety guard, fallback NLU, and chart selection. These do not require
an LLM API key -- they exercise the code paths that must be correct
regardless of which model (or no model at all) is behind the agent.

Run with: pytest tests/test_pipeline.py -v
"""
import pandas as pd
import pytest

from app.agents.fallback_nlu import plan_query
from app.data.profiler import profile_dataframe
from app.security.sql_guard import SQLGuardError, validate_and_prepare
from app.tools.chart_tool import select_chart


@pytest.fixture
def sample_df() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "order_date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-02", "2024-02-01"]),
            "region": ["North", "South", None, "North"],
            "revenue": [100.0, 200.0, 150.0, 300.0],
        }
    )
    return pd.concat([df, df.iloc[[0]]], ignore_index=True)  # inject one duplicate row


@pytest.fixture
def profile(sample_df) -> dict:
    return profile_dataframe(sample_df)


class TestProfiler:
    def test_shape_and_duplicates(self, profile):
        assert profile["n_rows"] == 5
        assert profile["n_cols"] == 3
        assert profile["duplicate_rows"] == 1

    def test_semantic_typing(self, profile):
        assert profile["numeric_columns"] == ["revenue"]
        assert profile["categorical_columns"] == ["region"]
        assert profile["date_columns"] == ["order_date"]

    def test_missing_value_detection(self, profile):
        region_col = next(c for c in profile["columns"] if c["name"] == "region")
        assert region_col["missing_count"] == 1

    def test_metric_and_date_heuristics(self, profile):
        assert profile["likely_metric_columns"] == ["revenue"]
        assert profile["likely_date_column"] == "order_date"


class TestSQLGuard:
    def test_allows_simple_select(self):
        result = validate_and_prepare("SELECT SUM(revenue) FROM data", allowed_tables=["data"])
        assert "SUM" in result.safe_sql
        assert result.tables_used == ["data"]

    def test_blocks_drop(self):
        with pytest.raises(SQLGuardError):
            validate_and_prepare("DROP TABLE data", allowed_tables=["data"])

    def test_blocks_stacked_statements(self):
        with pytest.raises(SQLGuardError):
            validate_and_prepare("SELECT 1; DROP TABLE data;", allowed_tables=["data"])

    def test_blocks_disallowed_table(self):
        with pytest.raises(SQLGuardError):
            validate_and_prepare("SELECT * FROM other_table", allowed_tables=["data"])

    def test_blocks_filesystem_functions(self):
        with pytest.raises(SQLGuardError):
            validate_and_prepare("SELECT * FROM read_csv_auto('/etc/passwd')", allowed_tables=["data"])

    def test_injects_limit(self):
        result = validate_and_prepare("SELECT * FROM data", allowed_tables=["data"], default_limit=100)
        assert "LIMIT 100" in result.safe_sql


class TestFallbackNLU:
    def _profile(self):
        return {
            "numeric_columns": ["revenue"],
            "categorical_columns": ["region"],
            "likely_metric_columns": ["revenue"],
            "likely_date_column": "order_date",
        }

    def test_total_pattern(self):
        plan = plan_query("What is the total revenue?", self._profile())
        assert "SUM(revenue)" in plan.sql

    def test_ranking_pattern(self):
        plan = plan_query("Which region has the highest revenue?", self._profile())
        assert "GROUP BY region" in plan.sql and "ORDER BY" in plan.sql

    def test_trend_pattern(self):
        plan = plan_query("Show me the monthly revenue trend", self._profile())
        assert "date_trunc" in plan.sql

    def test_unmatched_question_is_low_confidence(self):
        plan = plan_query("xyzzy quibble frobnicate", self._profile())
        assert plan.low_confidence is True


class TestChartSelection:
    def test_single_value_is_stat(self):
        df = pd.DataFrame({"total_revenue": [750.0]})
        assert select_chart(df)["type"] == "stat"

    def test_category_breakdown_is_bar(self):
        df = pd.DataFrame({"region": ["North", "South"], "total_revenue": [400.0, 350.0]})
        assert select_chart(df)["type"] == "bar"

    def test_multi_point_trend_is_line(self):
        df = pd.DataFrame({"month": ["2024-01-01", "2024-02-01", "2024-03-01"], "total_revenue": [400.0, 350.0, 500.0]})
        assert select_chart(df)["type"] == "line"
