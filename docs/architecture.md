# Architecture

## Request flow

```
Upload/Sample                         Question
     |                                    |
     v                                    v
ingest_file()/ingest_dataframe()    POST /api/chat
     |                                    |
     v                                    v
validate ext/size -> read -> clean   run_pipeline() [LangGraph]
     |                                    |
     v                    +---------------+----------------+
profile_dataframe()       |               plan               |
     |                    |    LLM (Groq/OpenAI/Anthropic)    |
     v                    |    or fallback_nlu.plan_query()   |
to_parquet()              +---------------+----------------+
     |                                    |
     v                                    v
generate_suggestions()               execute (DuckDB)
     |                                    |
     v                         error? --- + --- ok?
ProfileResponse                  |                 |
                                  v                 |
                             fix_sql (LLM)          |
                                  |                 |
                                  +--> execute ------+
                                                     |
                                                     v
                                              finalize:
                                        select_chart() [deterministic]
                                        generate_insight() [Python facts + LLM phrasing]
                                                     |
                                                     v
                                              ChatResponse
```

## Why DuckDB + Parquet, not "hold the DataFrame in memory forever"

Uploaded files are converted to Parquet once, on upload. Every chat turn opens a
fresh in-memory DuckDB connection and registers the Parquet file as a view. This
means:

- The FastAPI process stays stateless per-request (no long-lived per-session
  DataFrame or DB connection to leak or corrupt).
- DuckDB's columnar execution scales to far larger files than "load the whole CSV
  into a pandas DataFrame and keep it in a Python dict" would, with no code change
  needed as file size grows.
- The LLM's context window only ever sees the *schema* (`schema_context_for_llm()`
  in `profiler.py`) and small query *results* -- never the raw rows. This is the
  same principle AWS's own Bedrock AgentCore data-analyst guidance highlights:
  keeping the dataset in the execution environment and returning only explicitly
  selected outputs to the model, rather than piping large tool results into context.

## Why a LangGraph state machine instead of one big prompt

Four distinct concerns, four distinct nodes, each independently testable:

1. **`plan`** -- question + schema + conversation history → SQL. This is the only
   node that needs "creativity," so it's the only one that calls the LLM with any
   real temperature.
2. **`execute`** -- SQL → guard → DuckDB → DataFrame or error. Pure mechanism, zero
   LLM involvement, fully deterministic and unit-testable.
3. **`fix_sql`** (conditional) -- only entered when `execute` produced an error and
   retries remain. This is the self-correction loop: the model sees its own failed
   SQL and the database's actual error message, not a vague "try again."
4. **`finalize`** -- DataFrame → chart type (deterministic, by shape/dtype) + facts
   (computed in Python) → sentence (LLM phrasing of pre-computed facts, or a
   template if no LLM is configured).

The routing function (`route_after_execute`) is the entire "agentic" decision in the
graph: retry if there's an error and budget remains, otherwise finalize. Keeping
the decision surface that small is deliberate -- it's the difference between an
agent whose behavior you can reason about in an interview and one that "does
something, usually."

## Why the LLM never computes the headline number

`insight.py`'s `compute_facts()` takes the DuckDB result DataFrame and computes the
headline value, the prior-period comparison, and the percent change using plain
pandas/Python arithmetic. `generate_insight()` then either asks the LLM to phrase
those already-computed facts into a sentence, or (no LLM / LLM failure) fills a
template. Either way, the number a user sees on screen came out of `SUM()`/`AVG()`
executed by DuckDB, never out of next-token prediction. This is the direct, concrete
answer to "how do you prevent hallucinated numbers?" -- not a policy, an
architectural guarantee.

## Why chart type is deterministic, not LLM-chosen

`chart_tool.select_chart()` looks at the *actual shape* of the result DataFrame --
row count, column count, whether a column looks date-like, whether there are 1 or 2+
numeric columns -- and picks a chart type from that. The LLM's `chart_hint` from the
planning step is accepted as an initial signal but the result shape can always
override it. This avoids the failure mode where a model asks for a line chart on a
single-row aggregate result.

## Conversational memory

`session_store.py` keeps an in-memory list of `ConversationTurn`s per `session_id`
(question, generated SQL, answer, facts). `history_text()` renders the last
`MAX_HISTORY_TURNS` as plain text and injects it into the SQL-generation prompt, so
"what about the month before that" resolves against the prior turn's resolved period
rather than needing the user to repeat context. This is intentionally simple
(no vector store, no summarization) because the practical window is small -- a
handful of turns is what "let's dig into this dataset together" conversations
actually need.
