# Resume copy + interview prep

## Resume bullets (pick one, tune to space)

**Longer (best for a project section with room):**
> Built and deployed a conversational Agentic AI Data Analyst (React/TypeScript,
> FastAPI, LangGraph, DuckDB) that converts natural-language business questions into
> validated SQL, with AST-based query sandboxing, self-correcting retry on execution
> errors, deterministic chart selection, conversational memory, and a 20-question
> benchmark evaluation harness with numeric-tolerance scoring.

**Shorter (one line):**
> Built a full-stack agentic data-analysis platform (React/FastAPI/LangGraph/DuckDB)
> that answers natural-language questions with validated, guard-railed SQL instead of
> LLM-generated numbers; deployed live with a benchmark-based accuracy evaluation.

**Impact-flavored (if you run the evaluator and want a number):**
> Built and deployed an agentic data-analyst web app converting natural language to
> validated SQL over user datasets; achieved N/20 (X%) accuracy on a custom
> ground-truth benchmark with self-correcting retries and AST-based SQL sandboxing.

Run `evaluation/evaluator.py` against your deployed instance and drop the real N/X in
before using the third bullet -- don't publish a number you haven't actually measured.

## Likely interview questions and how to answer them (from what you built)

**"How do you know the LLM's answer is correct?"**
It doesn't compute the answer. It only generates SQL, which passes an AST-based guard
(`sql_guard.py`) before executing on DuckDB. The actual query result — not the model —
is what Python uses to compute the headline number and any comparison. The LLM's only
remaining job is phrasing that pre-computed number into a sentence
(`insight.py::generate_insight`).

**"What happens if the generated SQL is wrong or malicious?"**
Two layers. Safety: `sqlglot`-based AST parsing rejects anything that isn't a single
SELECT against the allowlisted table, blocks DDL/DML and filesystem-touching
functions (`read_csv`, `system`, etc.), and auto-injects a LIMIT. Correctness: if the
guard-approved query still fails at execution (bad column, type mismatch), the error
is fed back to the model for one retry via the LangGraph `fix_sql` node, capped at
`MAX_SQL_RETRIES`.

**"Why DuckDB instead of just pandas?"**
Files are converted to Parquet once on upload; each question opens a stateless DuckDB
connection over that Parquet file rather than holding the full DataFrame in a
long-lived process-level dict. That's what lets the same code path handle a 50MB file
without a rewrite, and it also keeps raw rows out of the LLM's context window --  the
model only ever sees a compact schema/profile string and small result sets.

**"What would you change with more time?"** (see `docs/ONE_DAY_BUILD_LOG.md` for the
full list) — PII detection before any data reaches the LLM, sandboxed Python execution
for statistics beyond what SQL expresses well (forecasting, anomaly detection), moving
session/dataset state out of in-memory Python dicts into Redis/Postgres for
multi-instance deployment, and a proper CI pipeline running the pytest suite and the
evaluation harness on every PR.

**"Why LangGraph instead of one big prompt / a simple while-loop?"**
The routing decision (retry vs. finalize) is the only place the pipeline branches, and
LangGraph makes that an explicit, inspectable edge rather than an if/else buried in a
larger function. It also cleanly separates a step that needs the LLM's creativity
(`plan`) from steps that are pure mechanism (`execute`, chart selection, fact
computation) — which made each of those independently unit-testable without needing
an API key (see `backend/tests/test_pipeline.py`).

**"Did you use AI to help build this?"**
Yes, be upfront about it — this whole app was built collaboratively with Claude in a
single focused session against a real same-day deadline. That's a legitimate,
increasingly expected way to build software quickly; what matters in the interview is
that you can explain every architectural decision above in your own words, because you
made those decisions and can defend them. If asked to modify the code live, you should
be able to navigate `orchestrator.py` and explain the graph without hesitation --
spend the time before the interview actually reading it, not just skimming this file.
