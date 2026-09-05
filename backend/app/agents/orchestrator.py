"""
Agent orchestrator: a LangGraph state machine implementing the
plan -> execute -> validate -> retry-on-error -> explain -> respond loop
described in the architecture doc.

    START
      |
      v
   [ plan ]  -- LLM (or deterministic fallback) turns the question into SQL
      |
      v
  [ execute ] -- AST-guarded, runs on DuckDB
      |
      +-- error & retries left --> [ fix_sql ] --> [ execute ]  (self-correction loop)
      |
      v (success, or retries exhausted)
  [ finalize ] -- deterministic chart selection + Python-computed insight facts
      |
      v
     END

Every node appends a human-readable step to `execution_trace`, which is
what powers the "Agent execution" observability panel in the UI -- safe
metadata about what happened, not the model's private chain-of-thought.
"""
from __future__ import annotations

import time
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.fallback_nlu import plan_query
from app.agents.insight import generate_insight
from app.agents.llm_client import ChatMessage, LLMClient, LLMError
from app.agents.prompts import (
    FIX_SQL_SYSTEM_PROMPT,
    FIX_SQL_USER_TEMPLATE,
    SQL_SYSTEM_PROMPT,
    SQL_USER_TEMPLATE,
)
from app.config import get_settings
from app.data.profiler import schema_context_for_llm
from app.security.sql_guard import SQLGuardError
from app.tools.chart_tool import select_chart
from app.tools.duckdb_tool import QueryExecutionError, QueryResult, run_query


class AgentState(TypedDict, total=False):
    question: str
    schema: str
    profile: dict
    history: str
    parquet_path: str
    sql: str | None
    chart_hint: str | None
    reasoning: str | None
    low_confidence: bool
    error: str | None
    retry_count: int
    max_retries: int
    result: QueryResult | None
    trace: list[dict[str, str]]
    used_llm: bool
    # final outputs
    answer: str
    chart: dict[str, Any]
    facts: dict[str, Any]
    execution_ms: float


def _trace(state: AgentState, label: str, detail: str, status: str = "ok") -> None:
    state.setdefault("trace", []).append({"label": label, "detail": detail, "status": status})


def node_plan(state: AgentState, llm: LLMClient) -> AgentState:
    question = state["question"]
    if llm.enabled:
        try:
            result = llm.chat_json(
                [
                    ChatMessage("system", SQL_SYSTEM_PROMPT),
                    ChatMessage(
                        "user",
                        SQL_USER_TEMPLATE.format(schema=state["schema"], history=state["history"], question=question),
                    ),
                ],
                temperature=0.1,
                max_tokens=500,
            )
            state["sql"] = result.get("sql", "")
            state["chart_hint"] = result.get("chart_hint", "table")
            state["reasoning"] = result.get("reasoning", "")
            state["low_confidence"] = False
            state["used_llm"] = True
            _trace(state, "Plan", f"LLM generated SQL for: \"{question}\"")
            return state
        except (LLMError, Exception) as exc:  # noqa: BLE001
            _trace(state, "Plan", f"LLM planning failed ({exc}); using deterministic fallback.", "retried")

    plan = plan_query(question, state["profile"])
    state["sql"] = plan.sql
    state["chart_hint"] = plan.chart_hint
    state["reasoning"] = plan.reasoning
    state["low_confidence"] = plan.low_confidence
    state["used_llm"] = False
    _trace(state, "Plan", f"Rule-based match: {plan.matched_pattern}")
    return state


def node_execute(state: AgentState) -> AgentState:
    sql = state.get("sql") or ""
    try:
        result = run_query(state["parquet_path"], sql, max_rows=get_settings().max_result_rows)
        state["result"] = result
        state["error"] = None
        _trace(state, "Execute", f"{result.row_count} row(s) in {result.execution_ms} ms", "ok")
    except SQLGuardError as exc:
        state["error"] = f"blocked by safety guard: {exc}"
        _trace(state, "Validate", str(exc), "error")
    except QueryExecutionError as exc:
        state["error"] = str(exc)
        _trace(state, "Execute", str(exc), "error")
    return state


def route_after_execute(state: AgentState) -> str:
    if state.get("error") and state.get("retry_count", 0) < state.get("max_retries", 2) and state.get("used_llm"):
        return "fix"
    return "finalize"


def node_fix_sql(state: AgentState, llm: LLMClient) -> AgentState:
    state["retry_count"] = state.get("retry_count", 0) + 1
    try:
        result = llm.chat_json(
            [
                ChatMessage("system", FIX_SQL_SYSTEM_PROMPT),
                ChatMessage(
                    "user",
                    FIX_SQL_USER_TEMPLATE.format(
                        schema=state["schema"], question=state["question"],
                        failed_sql=state.get("sql", ""), error=state.get("error", ""),
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=400,
        )
        state["sql"] = result.get("sql", state.get("sql"))
        _trace(state, "Self-correct", f"Retry {state['retry_count']}: regenerated SQL after error.", "retried")
    except Exception as exc:  # noqa: BLE001
        _trace(state, "Self-correct", f"Retry {state['retry_count']} failed to get a fix: {exc}", "error")
    return state


def node_finalize(state: AgentState, llm: LLMClient) -> AgentState:
    if state.get("error") and not state.get("result"):
        state["answer"] = (
            "I couldn't safely answer that question against this dataset "
            f"({state['error']}). Try rephrasing, or ask about one of the suggested questions."
        )
        state["chart"] = {"type": "empty"}
        state["facts"] = {}
        _trace(state, "Respond", "Returned error message after exhausting retries.", "error")
        return state

    result: QueryResult = state["result"]
    chart = select_chart(result.dataframe, hint=state.get("chart_hint"))
    answer, facts = generate_insight(state["question"], result.dataframe, llm)

    state["chart"] = chart
    state["facts"] = facts
    state["answer"] = answer
    _trace(state, "Insight", "Computed facts in Python; LLM only phrased the sentence." if llm.enabled
           else "Computed facts in Python; template phrasing (no LLM configured).")
    _trace(state, "Respond", "Final answer assembled.")
    return state


def build_graph(llm: LLMClient):
    graph = StateGraph(AgentState)
    graph.add_node("plan", lambda s: node_plan(s, llm))
    graph.add_node("execute", node_execute)
    graph.add_node("fix_sql", lambda s: node_fix_sql(s, llm))
    graph.add_node("finalize", lambda s: node_finalize(s, llm))

    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_conditional_edges("execute", route_after_execute, {"fix": "fix_sql", "finalize": "finalize"})
    graph.add_edge("fix_sql", "execute")
    graph.add_edge("finalize", END)
    return graph.compile()


def run_pipeline(
    question: str,
    profile: dict,
    parquet_path: str,
    history: str,
    llm: LLMClient,
) -> AgentState:
    app_graph = build_graph(llm)
    start = time.perf_counter()
    initial: AgentState = {
        "question": question,
        "schema": schema_context_for_llm(profile),
        "profile": profile,
        "history": history,
        "parquet_path": parquet_path,
        "retry_count": 0,
        "max_retries": get_settings().max_sql_retries,
        "trace": [],
    }
    final_state = app_graph.invoke(initial)
    final_state["execution_ms"] = round((time.perf_counter() - start) * 1000, 2)
    return final_state
