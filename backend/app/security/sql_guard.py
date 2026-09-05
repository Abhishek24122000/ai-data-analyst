"""
AST-based SQL safety guard.

The LLM only ever produces SQL text; nothing it writes is trusted until it
passes through here. Uses sqlglot to actually parse the statement (rather
than regex keyword-blocking, which is trivially bypassed with comments /
casing / whitespace tricks) and enforces:

  1. Exactly one statement (no `; DROP TABLE ...` stacking).
  2. The statement is a SELECT (optionally with CTEs) -- no DDL/DML.
  3. Every table referenced is in the caller-supplied allowlist.
  4. No banned function/keyword calls (e.g. PRAGMA, ATTACH, read_csv,
     COPY) that could touch the filesystem or other databases.
  5. A LIMIT is present (auto-injected if the model forgot one) so a
     careless `SELECT *` on a large table can't blow up the response.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

def _banned_types() -> tuple[type, ...]:
    """Built defensively via getattr: not every sqlglot version ships every
    expression class (e.g. `Attach` was added for DuckDB support in later
    releases), so a missing name should never crash the guard at import
    time -- it should just mean one less specific class to check, while
    `exp.Command` (present in all versions) still catches most of the
    same statements (PRAGMA/ATTACH/COPY/VACUUM/INSTALL/LOAD/EXPORT/IMPORT)
    as an unrecognized-keyword fallback."""
    names = ["Insert", "Update", "Delete", "Drop", "Create", "Alter", "Attach", "Copy", "Command"]
    return tuple(getattr(exp, n) for n in names if hasattr(exp, n))


BANNED_STATEMENT_TYPES = _banned_types()

BANNED_FUNCTIONS = {
    "read_csv", "read_csv_auto", "read_json", "read_json_auto", "read_parquet",
    "glob", "system", "pragma_version",
}


class SQLGuardError(ValueError):
    pass


@dataclass
class GuardResult:
    safe_sql: str
    tables_used: list[str]


def validate_and_prepare(sql: str, allowed_tables: list[str], default_limit: int = 5000) -> GuardResult:
    sql = sql.strip().rstrip(";")
    if not sql:
        raise SQLGuardError("Empty SQL.")

    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception as exc:  # noqa: BLE001
        raise SQLGuardError(f"SQL failed to parse: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLGuardError("Only a single SELECT statement is allowed.")

    tree = statements[0]

    if isinstance(tree, BANNED_STATEMENT_TYPES):
        raise SQLGuardError(f"Statement type '{type(tree).__name__}' is not allowed. Only SELECT is permitted.")

    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        raise SQLGuardError("Only SELECT queries (optionally with CTEs / UNION) are allowed.")

    # Function allowlist check
    for func in tree.find_all(exp.Func):
        fname = (func.sql_name() or func.key or "").lower()
        if fname in BANNED_FUNCTIONS:
            raise SQLGuardError(f"Function '{fname}' is not permitted in generated queries.")

    # Table allowlist check
    allowed = {t.lower() for t in allowed_tables}
    tables_used = []
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        # Skip CTE references (they aren't "real" tables)
        cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
        if name in cte_names:
            continue
        tables_used.append(name)
        if name not in allowed:
            raise SQLGuardError(
                f"Table '{name}' is not in the allowed table list ({', '.join(sorted(allowed))})."
            )

    # Auto-inject a LIMIT if the top-level SELECT doesn't have one.
    if isinstance(tree, exp.Select) and tree.args.get("limit") is None:
        tree = tree.limit(default_limit)

    safe_sql = tree.sql(dialect="duckdb")
    return GuardResult(safe_sql=safe_sql, tables_used=list(dict.fromkeys(tables_used)))
