"""Live-database integration test for Phase 4.

Skipped automatically when DATABASE_URL isn't reachable (same pattern as
test_warehouse_integration.py -- see that file for why this is one long
test function rather than several sharing a fixture). When it can run:
migrates and seeds the warehouse, then exercises app.validator.executor
and the full app.pipeline repair loop against the real bi_readonly role --
including the ultimate proof that adversarial SQL never executes: a
FakeLLMProvider that always tries to DROP the task table gets exhausted by
the repair loop, and the table is still there afterward with every row.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db.seed import ANOMALY_DEPARTMENT, ANOMALY_SUBTYPE, ANOMALY_TASKTYPE, seed_database
from app.llm.fake import FakeLLMProvider
from app.pipeline import answer_question
from app.validator.executor import execute_readonly

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

_REAL_QUERY_SQL = (
    "SELECT to_char(createddatetime, 'YYYY') || '-Q' || to_char(createddatetime, 'Q') AS quarter, "
    "percentile_cont(0.5) WITHIN GROUP (ORDER BY assignee_hold_hrs) AS median_hold_hrs "
    "FROM analytics.v_task_lifecycle "
    "WHERE department_name = :department AND tasktype = :tasktype AND tasksubtype = :subtype "
    "AND assignee_hold_hrs IS NOT NULL GROUP BY 1"
)


def _real_query_response(*, department: str, tasktype: str, subtype: str) -> str:
    return json.dumps(
        {
            "sql": _REAL_QUERY_SQL,
            "dialect": "postgres",
            "referenced_objects": ["analytics.v_task_lifecycle"],
            "assumptions": [],
            "parameters": {"department": department, "tasktype": tasktype, "subtype": subtype},
            "confidence": 0.9,
        }
    )


_DROP_TABLE_RESPONSE = json.dumps(
    {
        "sql": "DROP TABLE marketplace.task",
        "dialect": "postgres",
        "referenced_objects": [],
        "assumptions": [],
        "parameters": {},
        "confidence": 0.5,
    }
)


async def test_validator_and_pipeline_end_to_end_after_migrate_and_seed() -> None:
    settings = get_settings()
    probe_engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with probe_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip(
            "DATABASE_URL is not reachable -- run `docker compose up -d db` "
            "(see README.md) to exercise this test for real."
        )
    finally:
        await probe_engine.dispose()

    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert migration.returncode == 0, migration.stderr

    admin_engine = create_async_engine(settings.DATABASE_URL)
    try:
        seeded = await seed_database(admin_engine)
        assert len(seeded.tasks) > 0
        async with admin_engine.connect() as conn:
            (expected_task_count,) = (
                await conn.execute(text("SELECT count(*) FROM marketplace.task"))
            ).one()
    finally:
        await admin_engine.dispose()

    # Everything below uses the read-only warehouse role, matching what
    # the real Validator Agent uses in production.
    readonly_engine = create_async_engine(settings.WAREHOUSE_URL)
    try:
        # --- executor: basic query, row limit, and timeout enforcement ---
        result = await execute_readonly(
            readonly_engine,
            "SELECT taskid FROM marketplace.task ORDER BY taskid",
            {},
            timeout_ms=10_000,
            row_limit=5_000,
        )
        assert result.row_count == expected_task_count
        assert not result.truncated

        small_limit_result = await execute_readonly(
            readonly_engine,
            "SELECT taskid FROM marketplace.task ORDER BY taskid",
            {},
            timeout_ms=10_000,
            row_limit=10,
        )
        assert small_limit_result.row_count == 10
        assert small_limit_result.truncated is True

        timeout_check = await execute_readonly(
            readonly_engine,
            "SELECT current_setting('statement_timeout') AS timeout",
            {},
            timeout_ms=4242,
            row_limit=1,
        )
        assert "4242" in str(timeout_check.rows[0][0])

        # --- full pipeline: a real question, answered correctly ---
        real_provider = FakeLLMProvider()
        real_provider.register(
            "hold time",
            _real_query_response(
                department=ANOMALY_DEPARTMENT, tasktype=ANOMALY_TASKTYPE, subtype=ANOMALY_SUBTYPE
            ),
        )
        pipeline_result = await answer_question(
            real_provider,
            readonly_engine,
            question="Why did median task hold time spike for the Buyer department in Q2?",
            dialect="postgres",
            retrieved_context=[],
            max_repairs=2,
            timeout_ms=10_000,
            row_limit=5_000,
        )
        assert pipeline_result.validator_output.status == "pass"
        assert pipeline_result.attempts == 1
        query_result = pipeline_result.validator_output.result
        assert query_result is not None
        quarter_index = query_result.columns.index("quarter")
        hold_hrs_index = query_result.columns.index("median_hold_hrs")
        by_quarter = {
            str(row[quarter_index]): float(row[hold_hrs_index])  # type: ignore[arg-type]
            for row in query_result.rows
        }
        baseline = [by_quarter[q] for q in ("2025-Q4", "2026-Q1", "2026-Q3") if q in by_quarter]
        assert baseline and "2026-Q2" in by_quarter
        assert by_quarter["2026-Q2"] > 2 * (sum(baseline) / len(baseline))

        # --- adversarial: a DROP TABLE attempt must never execute, even
        # after exhausting every repair attempt ---
        hostile_provider = FakeLLMProvider()
        hostile_provider.register("hold time", _DROP_TABLE_RESPONSE)  # same reply every retry
        hostile_result = await answer_question(
            hostile_provider,
            readonly_engine,
            question="Why did median task hold time spike for the Buyer department in Q2?",
            dialect="postgres",
            retrieved_context=[],
            max_repairs=2,
            timeout_ms=10_000,
            row_limit=5_000,
        )
        assert hostile_result.validator_output.status == "fail"
        assert hostile_result.attempts == 3  # 1 initial + 2 repairs, all rejected
        assert len(hostile_provider.calls) == 3

        async with readonly_engine.connect() as conn:
            (surviving_task_count,) = (
                await conn.execute(text("SELECT count(*) FROM marketplace.task"))
            ).one()
        assert surviving_task_count == expected_task_count
    finally:
        await readonly_engine.dispose()
