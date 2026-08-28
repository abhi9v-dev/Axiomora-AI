"""Live-database integration test for Phase 1.

Skipped automatically when DATABASE_URL isn't reachable (e.g.
`docker compose up -d db` hasn't been run yet -- see README.md). When it
can run, it applies the real migration, seeds real data, and queries the
real analytics.v_task_lifecycle view and the real bi_readonly role, so it
is the actual end-to-end proof that the offline-SQL test and the
pure-Python generator test cannot provide on their own.

Deliberately written as one long test function rather than several tests
sharing a fixture, to avoid async-fixture/event-loop-scope edge cases that
could not be verified in the environment this phase was built in (no local
Postgres was available -- see docs/progress.md).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db.seed import ANOMALY_DEPARTMENT, ANOMALY_SUBTYPE, ANOMALY_TASKTYPE, seed_database

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

_HOLD_TIME_BY_QUARTER_SQL = text("""
    SELECT
        to_char(createddatetime, 'YYYY') || '-Q' || to_char(createddatetime, 'Q') AS quarter,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY assignee_hold_hrs) AS median_hold_hrs
    FROM analytics.v_task_lifecycle
    WHERE department_name = :department
      AND tasktype = :tasktype
      AND tasksubtype = :subtype
      AND assignee_hold_hrs IS NOT NULL
    GROUP BY 1
    """)


async def test_warehouse_end_to_end_after_migrate_and_seed() -> None:
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

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        seeded = await seed_database(engine)
        assert len(seeded.tasks) > 0

        async with engine.connect() as conn:
            (view_row_count,) = (
                await conn.execute(text("SELECT count(*) FROM analytics.v_task_lifecycle"))
            ).one()
            assert view_row_count == len(seeded.tasks)

            result = await conn.execute(
                _HOLD_TIME_BY_QUARTER_SQL,
                {
                    "department": ANOMALY_DEPARTMENT,
                    "tasktype": ANOMALY_TASKTYPE,
                    "subtype": ANOMALY_SUBTYPE,
                },
            )
            by_quarter = {row.quarter: float(row.median_hold_hrs) for row in result}

        baseline_quarters = [q for q in ("2025-Q4", "2026-Q1", "2026-Q3") if q in by_quarter]
        assert baseline_quarters, "expected baseline quarters in seeded data"
        assert "2026-Q2" in by_quarter
        baseline_median = sum(by_quarter[q] for q in baseline_quarters) / len(baseline_quarters)
        assert by_quarter["2026-Q2"] > 2 * baseline_median, (
            "Q2 Buyer/Compliance Review hold time should spike well above baseline: "
            f"{by_quarter}"
        )
    finally:
        await engine.dispose()

    # The read-only role can read the view but cannot write to base tables.
    readonly_engine = create_async_engine(settings.WAREHOUSE_URL)
    try:
        async with readonly_engine.connect() as conn:
            (readonly_count,) = (
                await conn.execute(text("SELECT count(*) FROM analytics.v_task_lifecycle"))
            ).one()
            assert readonly_count == len(seeded.tasks)

            with pytest.raises(DBAPIError):
                async with conn.begin():
                    await conn.execute(text("DELETE FROM marketplace.task"))
    finally:
        await readonly_engine.dispose()
