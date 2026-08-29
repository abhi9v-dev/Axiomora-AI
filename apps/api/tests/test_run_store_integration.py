"""Live-database integration test for app.orchestrator.store.

Skipped automatically when DATABASE_URL isn't reachable, same pattern as
every other live-DB test in this suite (see test_warehouse_integration.py
for why). When it can run: migrates, then round-trips a RunSnapshot
(including its nested NL2SQL/Validator/Insight JSONB) through
create_run/save_run/get_run/list_runs against the real `runs.run` table.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.schema import RetrievalResult
from app.config import get_settings
from app.insight.schema import InsightOutput
from app.nl2sql.schema import NL2SQLOutput
from app.orchestrator.schema import AttemptRecord, RunSnapshot
from app.orchestrator.store import create_run, get_run, list_runs, save_run
from app.validator.schema import QueryResult, ValidationCheck, ValidatorOutput

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def _snapshot(**overrides: object) -> RunSnapshot:
    now = dt.datetime.now(dt.UTC)
    defaults: dict[str, object] = dict(
        run_id=uuid.uuid4(),
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status="RECEIVED",
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return RunSnapshot.model_validate(defaults)


async def test_run_store_round_trip_end_to_end() -> None:
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
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        snapshot = _snapshot()
        async with session_factory() as session:
            await create_run(session, snapshot)

        async with session_factory() as session:
            fetched = await get_run(session, snapshot.run_id)
        assert fetched is not None
        assert fetched.run_id == snapshot.run_id
        assert fetched.status == "RECEIVED"
        assert fetched.attempts == []
        assert fetched.insight is None

        nl2sql = NL2SQLOutput(
            sql="SELECT 1",
            dialect="postgres",
            referenced_objects=["analytics.v_task_lifecycle"],
            assumptions=[],
            parameters={},
            confidence=0.9,
        )
        validator = ValidatorOutput(
            status="pass",
            checks=[ValidationCheck(name="sql_policy", status="pass", details="ok")],
            repairable=False,
            result=QueryResult(columns=["x"], rows=[[1]], row_count=1, truncated=False),
        )
        insight = InsightOutput(headline="h", narrative="n")
        updated = fetched.model_copy(
            update={
                "status": "READY",
                "retrieved_context": [
                    RetrievalResult(
                        chunk_id=1,
                        document_id=1,
                        kind="table",
                        object_name="analytics.v_task_lifecycle",
                        title="View",
                        content="content",
                        score=0.9,
                        citation="catalog:table:analytics.v_task_lifecycle:chunk:0",
                    )
                ],
                "attempts": [AttemptRecord(attempt_no=1, nl2sql=nl2sql, validator=validator)],
                "insight": insight,
                "updated_at": dt.datetime.now(dt.UTC),
                "completed_at": dt.datetime.now(dt.UTC),
            }
        )
        async with session_factory() as session:
            await save_run(session, updated)

        async with session_factory() as session:
            reloaded = await get_run(session, snapshot.run_id)
        assert reloaded is not None
        assert reloaded.status == "READY"
        assert len(reloaded.attempts) == 1
        assert reloaded.attempts[0].nl2sql.sql == "SELECT 1"
        assert reloaded.attempts[0].validator.status == "pass"
        assert reloaded.insight is not None
        assert reloaded.insight.headline == "h"
        assert reloaded.retrieved_context[0].object_name == "analytics.v_task_lifecycle"

        async with session_factory() as session:
            history = await list_runs(session, tenant_id="default", limit=10)
        assert any(item.run_id == snapshot.run_id for item in history)
    finally:
        await engine.dispose()
