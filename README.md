# AI Data Analyst Agent

A conversational, agentic data-analysis tool: upload a CSV/Excel file (or load the
built-in sample dataset), get automatic profiling and suggested questions, then ask
natural-language questions and get answers backed by **validated SQL execution**, not
LLM guesswork.

> Built and deployed a conversational Agentic AI Data Analyst that converts
> natural-language business questions into validated SQL analytical workflows over
> user-uploaded datasets, with autonomous EDA, self-correcting query generation,
> AST-based SQL sandboxing, conversational memory, and a benchmark-based evaluation
> harness.

See [`docs/resume_bullet.md`](docs/resume_bullet.md) for ready-to-use resume copy and
likely interview questions with prepared answers.

## Why this is more than "ChatGPT + pandas"

The one thing every reviewer of this repo will ask is *"how do you know the answer is
correct?"* The answer is architectural, not a promise:

1. The LLM **never computes a number**. It only ever produces SQL.
2. Every generated SQL statement passes through an **AST-based safety guard**
   ([`sql_guard.py`](backend/app/security/sql_guard.py), built on `sqlglot`) before it
   touches the database -- single-statement, SELECT-only, table-allowlisted,
   function-blocklisted, auto-`LIMIT`ed.
3. The query actually executes against **DuckDB**, and the *DataFrame result* -- not
   the LLM -- is what Python uses to compute the headline number, the comparison, and
   the percent change ([`insight.py`](backend/app/agents/insight.py)).
4. The LLM's only remaining job is to phrase those pre-computed facts into a sentence.
   If it fails, or if no LLM is configured at all, a template does the phrasing
   instead -- **the app never breaks for lack of an API key**, it degrades to a
   deterministic rule-based query planner ([`fallback_nlu.py`](backend/app/agents/fallback_nlu.py)).
5. If the generated SQL fails to execute, a LangGraph retry edge feeds the error back
   to the model for **self-correction** (up to `MAX_SQL_RETRIES`, default 2) before
   giving up.

## Architecture

```
 Browser (React/TS/Recharts)
        |  HTTPS/JSON
        v
 FastAPI backend  ── /api/upload, /api/sample, /api/chat ──
        |
        v
 LangGraph agent state machine
   plan -> execute -> (error? -> fix_sql -> execute) -> finalize
        |                                        |
        v                                        v
   DuckDB (Parquet, AST-guarded SQL)     Python-computed facts
        |                                        |
        v                                        v
   Deterministic chart-type selection     LLM phrasing (or template)
```

Full write-up, including why DuckDB-over-Parquet instead of holding the whole
DataFrame in memory, and the reasoning behind each LangGraph node, is in
[`docs/architecture.md`](docs/architecture.md).

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React + TypeScript + Vite + Tailwind + Recharts | Real frontend engineering, not a Streamlit demo |
| Backend | FastAPI | Async Python API layer |
| Agent orchestration | LangGraph | Stateful plan/execute/retry graph, not a single monolithic prompt |
| Data engine | DuckDB + Parquet | Columnar SQL execution; raw rows never enter the LLM context |
| LLM | Provider-agnostic (Groq free tier / OpenAI / Anthropic) | One env var swaps providers; app runs with zero LLM cost via Groq |
| SQL safety | `sqlglot` AST validation | Real parsing, not regex keyword-blocking |
| Evaluation | Custom HTTP-based benchmark harness | 20 ground-truth questions, numeric-tolerance scoring |

## Project structure

```
ai-data-analyst/
├── backend/            FastAPI + LangGraph + DuckDB
│   ├── app/
│   │   ├── agents/      LLM client, prompts, orchestrator, insight, suggestions, fallback NLU
│   │   ├── data/        ingestion, profiler, synthetic sample dataset
│   │   ├── security/    AST-based SQL guard
│   │   └── tools/       DuckDB execution, chart-type selection
│   └── tests/           pytest unit tests (guard, profiler, fallback NLU, charts)
├── frontend/            React + TS + Vite + Tailwind + Recharts
├── evaluation/          benchmark_questions.json + evaluator.py
├── docs/                architecture, resume bullets, build log
├── render.yaml          one-click-ish backend deploy config
└── docker-compose.yml   run both services locally with one command
```

## Running it locally

### 1. Get a free LLM key (optional but recommended, ~1 minute, no cost)

The default provider is **Groq** -- free tier, OpenAI-compatible, fast Llama models.
Sign up at https://console.groq.com, create an API key, and you're done. Without a
key, the backend still runs -- it just uses the deterministic fallback query planner
instead of full natural-language understanding (see "Zero-key mode" below).

### 2. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your LLM_API_KEY (or leave LLM_PROVIDER=none)
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Open http://localhost:5173, click **"Load sample sales dataset"**, and start asking
questions -- try one of the suggested questions in the left panel first.

### Or: one command with Docker Compose

```bash
docker compose up --build
```

## Zero-key mode

Set `LLM_PROVIDER=none` (or just leave `LLM_API_KEY` blank) and the backend falls back
to [`fallback_nlu.py`](backend/app/agents/fallback_nlu.py) -- a small, honest
pattern-matcher that handles totals, averages, group-by rankings, monthly trends, and
row counts against whatever columns your dataset actually has. It won't handle
open-ended questions well, and the UI shows a banner saying so, but the whole
pipeline -- profiling, SQL guard, DuckDB execution, chart selection, conversational
memory -- still runs end to end with zero API cost. This is also what makes the app
demoable/testable without ever touching a paid API.

## Security

- **SQL injection / stacked statements**: blocked by AST parsing (`sqlglot`), not
  regex. `SELECT 1; DROP TABLE data;` fails to validate as a single SELECT.
- **DDL/DML**: `INSERT`/`UPDATE`/`DELETE`/`DROP`/`CREATE`/`ALTER` are rejected by
  statement-type check.
- **Filesystem/network access from SQL**: DuckDB table-function calls like
  `read_csv`, `read_parquet`, `glob`, `system` are blocklisted.
- **Table scope**: only the `data` view (the uploaded dataset) is queryable; any
  other table reference is rejected.
- **Upload validation**: extension allowlist, file-size cap (`MAX_UPLOAD_MB`, default
  50 MB).
- **Result size cap**: every query gets an auto-injected `LIMIT` if the model didn't
  include one.

Not yet implemented (see [`docs/ONE_DAY_BUILD_LOG.md`](docs/ONE_DAY_BUILD_LOG.md) for
the full "what I'd add with more time" list): PII detection/redaction, per-user auth,
rate limiting, sandboxed Python execution for advanced statistics.

## Evaluation

```bash
cd evaluation
python3 evaluator.py --base-url http://localhost:8000 --out results/run1.json
```

Runs 20 ground-truth questions (aggregation, ranking, time-series, data-quality,
conversational follow-ups) against the sample dataset and reports pass/fail with a
numeric tolerance, plus average latency. Expected values were computed independently
with pandas against the same fixed random seed used to generate the sample dataset
(see [`backend/app/data/sample_data.py`](backend/app/data/sample_data.py)), so they're
ground truth, not "whatever the model said last time."

## Deployment (free tier)

- **Backend** → [Render](https://render.com) free web service. `render.yaml` at the
  repo root is pre-configured (Docker runtime, health check, env vars). Push to a
  GitHub repo, connect it on Render, set `LLM_API_KEY` in the dashboard. Free-tier
  services spin down after inactivity, so the first request after idle will be slow
  (a few seconds) -- expected and fine for a portfolio demo.
- **Frontend** → [Vercel](https://vercel.com) free (Hobby) tier. Import the repo,
  set root directory to `frontend`, set `VITE_API_BASE_URL` to your Render backend
  URL.

Step-by-step instructions: [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Known limitations (by design, for a one-day build)

- Session/dataset storage is in-memory (`session_store.py`) -- fine for a single
  Render instance demo, would move to Redis/Postgres for multi-instance production.
- No authentication -- anyone with the URL can upload/query. Fine for a portfolio
  demo, not for real user data.
- Fallback NLU covers common patterns only, not general natural language, by design
  (see "Zero-key mode" above).
- Python-sandboxed statistical analysis (forecasting, anomaly detection) is scoped
  out -- SQL covers the MVP question set.

This is deliberate scope-cutting under a real deadline, not an oversight -- see
[`docs/ONE_DAY_BUILD_LOG.md`](docs/ONE_DAY_BUILD_LOG.md) for the full reasoning and
what V2 would add.
