"""Read-only SQL execution against the warehouse (the bi_readonly role, via
Settings.WAREHOUSE_URL).

Only ever called with SQL that has already passed
app.validator.policy.validate_sql_policy -- this module trusts its input
completely and does no policy checking of its own; callers (app.validator.agent)
are responsible for validating first. Enforces a per-statement timeout and a
row limit, fetching one extra row so truncation is reported rather than
silently dropping data the caller doesn't know is incomplete.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.validator.schema import QueryResult


async def execute_readonly(
    engine: AsyncEngine,
    sql: str,
    parameters: dict[str, object],
    *,
    timeout_ms: int,
    row_limit: int,
) -> QueryResult:
    async with engine.connect() as conn, conn.begin():
        # Postgres's SET does not accept a bind parameter -- it requires a
        # literal. Safe here specifically because timeout_ms comes from our
        # own Settings (never user/model input) and is int-cast first.
        await conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))

        result = await conn.execute(text(sql), parameters)
        columns = list(result.keys())
        rows = result.fetchmany(row_limit + 1)

    truncated = len(rows) > row_limit
    limited_rows = rows[:row_limit]
    return QueryResult(
        columns=columns,
        rows=[list(row) for row in limited_rows],
        row_count=len(limited_rows),
        truncated=truncated,
    )
