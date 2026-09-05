# One-day build log: what shipped vs. the original 10-week plan

You came in with a much larger architecture (multi-agent LangGraph orchestration,
PostgreSQL sessions, S3 storage, Bedrock/AWS deployment, PII detection, sandboxed
Python execution, Terraform, CI/CD, a 100-question benchmark) and a real same-day
deadline. Here's what got built today, what got deliberately cut, and why -- so you
can speak to the scoping decision itself in an interview, which is its own signal.

## Shipped today

- FastAPI backend, DuckDB + Parquet data engine, AST-based SQL safety guard
  (`sqlglot`), provider-agnostic LLM client (Groq free tier by default, OpenAI/
  Anthropic as drop-in swaps).
- LangGraph agent: plan → execute → conditional self-correction retry → finalize.
- Deterministic dataset profiler (schema, missing values, duplicates, correlations,
  numeric/categorical/date typing) that also doubles as the LLM's schema context --
  raw rows never enter the model's context window.
- Auto-generated suggested questions (LLM-backed with a heuristic fallback).
- Conversational memory (in-memory, per-session, last N turns).
- Deterministic chart-type selection (not LLM-chosen) + React/TypeScript/Recharts
  frontend, not Streamlit.
- Zero-cost "fallback mode": a small deterministic query planner so the whole
  pipeline runs and is demoable/testable with no LLM API key at all.
- 20-question evaluation harness with pandas-verified ground-truth answers and
  numeric-tolerance scoring, runnable against any deployed instance over HTTP.
- pytest unit tests for the guard, profiler, fallback NLU, and chart selection.
- Deploy configs for Render (backend) + Vercel (frontend), both free tier.

## Deliberately cut for today (this is the honest "V2" list, not a cop-out)

| Cut | Why it's safe to cut for a resume MVP | What V2 would do |
|---|---|---|
| PostgreSQL / Redis for sessions | In-memory dict is correct for a single-instance demo; swapping it is a well-understood, bounded follow-up task, not a design risk | `session_store.py` behind an interface, swap the in-memory dict for Redis |
| PII detection | No real user data in a portfolio demo | A regex/NER pass on ingestion flagging likely PII columns before they reach the LLM context |
| Sandboxed Python execution for stats | SQL via DuckDB covers the whole MVP question set (aggregation, ranking, trend, comparison) | AST-restricted Python execution (whitelist pandas/numpy/scipy, block os/subprocess/socket) for forecasting/anomaly detection questions SQL can't express well |
| AWS deployment (Lambda/S3/Bedrock) | Free-tier Render+Vercel gets a live URL today with near-zero risk of surprise billing; AWS setup/IAM/billing alone can eat the whole day | Terraform-defined Lambda+S3+CloudFront once the app's traffic/scale actually justifies it |
| CI/CD pipeline | Not needed for a single-day ship; the test suite exists and runs locally | GitHub Actions: pytest + evaluator.py on every PR, Docker build check |
| 100-question benchmark | 20 well-chosen, pandas-verified questions across 5 categories demonstrate the same evaluation *methodology* in a fraction of the time | Expand to 100 across more edge cases (joins across multiple uploaded datasets, ambiguous phrasing, adversarial SQL-injection-flavored questions) |
| Multi-dataset joins | Single-dataset Q&A is the core loop; joins are a real feature, not a today-sized one | Allow multiple uploads, let the planner reference multiple tables, extend the guard's allowlist accordingly |

## Environment note (a real thing that happened today, worth knowing)

The sandbox this was built in had outbound network access to package registries
(PyPI, npm) blocked entirely, so dependencies could not be `pip install`ed or
`npm install`ed and the full stack could not be run end-to-end inside that sandbox.
What was verified instead:

- Every backend `.py` file passed `python -m py_compile` (syntax-valid).
- The modules with no missing-dependency blockers -- `profiler.py`, `chart_tool.py`,
  `fallback_nlu.py`, `sample_data.py` -- were actually executed with real pandas/
  numpy (which *were* preinstalled) against constructed test cases, catching and
  fixing one real bug in chart-type selection along the way (a 2-point trend
  defaulting to a line chart instead of the intended comparison-bar chart).
- The frontend TypeScript was type-checked with a global `tsc` install (filtering out
  the expected "module not found" noise from not having `npm install`ed
  project-local packages).
- The full FastAPI + DuckDB + LangGraph stack, and the frontend's actual `npm run
  dev`, have **not** been run end-to-end yet -- do that first, locally, before you
  demo or deploy this. `pip install -r backend/requirements.txt` and `npm install` in
  `frontend/` on your own machine should work normally; only this build sandbox's
  network was restricted.

Mentioning this honestly if it comes up is a better interview answer than pretending
everything was tested end-to-end when it wasn't -- and "here's exactly what I
verified and how, and here's what still needs a real run" is itself a decent
engineering-judgment story.
