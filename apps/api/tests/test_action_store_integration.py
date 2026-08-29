"""Live-database integration test for app.action.store.

Skipped automatically when DATABASE_URL isn't reachable, same pattern as
every other live-DB test in this suite. When it can run: migrates,
creates a runs.run row to satisfy the FK, then round-trips an
ActionRecord through record_action/get_action_by_idempotency_key/
list_actions against the real `runs.action` table -- including that the
database-level unique constraint (run_id, idempotency_key) actually
rejects a second insert with the same key, which is what
app.api.actions's IntegrityError handling relies on.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.action.schema import ActionRecord
from app.action.store import (
    get_action_by_idempotency_key,
    list_actions,
    record_action,
    update_action_outcome,
)
from app.config import get_settings
from app.orchestrator.schema import RunSnapshot
from app.orchestrator.store import create_run

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def _run_snapshot() -> RunSnapshot:
    now = dt.datetime.now(dt.UTC)
    return RunSnapshot(
        run_id=uuid.uuid4(),
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status="READY",
        created_at=now,
        updated_at=now,
    )


def _action_record(run_id: uuid.UUID, idempotency_key: str) -> ActionRecord:
    return ActionRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        type="export_excel",
        destination="download",
        status="completed",
        idempotency_key=idempotency_key,
        approved_by="result_owner",
        rejection_reason=None,
        created_at=dt.datetime.now(dt.UTC),
    )


async def test_action_store_round_trip_and_unique_constraint() -> None:
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
        run_snapshot = _run_snapshot()
        async with session_factory() as session:
            await create_run(session, run_snapshot)

        record = _action_record(run_snapshot.run_id, "key-1")
        async with session_factory() as session:
            await record_action(session, record)

        async with session_factory() as session:
            fetched = await get_action_by_idempotency_key(session, run_snapshot.run_id, "key-1")
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.status == "completed"

        async with session_factory() as session:
            missing = await get_action_by_idempotency_key(
                session, run_snapshot.run_id, "no-such-key"
            )
        assert missing is None

        duplicate = _action_record(run_snapshot.run_id, "key-1")
        with pytest.raises(IntegrityError):
            async with session_factory() as session:
                await record_action(session, duplicate)

        different_key = _action_record(run_snapshot.run_id, "key-2")
        async with session_factory() as session:
            await record_action(session, different_key)

        async with session_factory() as session:
            actions = await list_actions(session, run_snapshot.run_id)
        assert {action.idempotency_key for action in actions} == {"key-1", "key-2"}

        # A retried Power BI action updates its existing row in place
        # (app.api.actions's failed-then-retried path) rather than
        # inserting a second one for the same idempotency key.
        async with session_factory() as session:
            updated = await update_action_outcome(
                session, record.id, status="failed", rejection_reason="simulated adapter error"
            )
        assert updated.status == "failed"
        assert updated.rejection_reason == "simulated adapter error"
        async with session_factory() as session:
            refetched = await get_action_by_idempotency_key(session, run_snapshot.run_id, "key-1")
        assert refetched is not None
        assert refetched.status == "failed"

        async with session_factory() as session:
            recovered = await update_action_outcome(
                session, record.id, status="completed", rejection_reason="Pushed 3 rows"
            )
        assert recovered.status == "completed"

        async with session_factory() as session:
            actions_after_retry = await list_actions(session, run_snapshot.run_id)
        assert len(actions_after_retry) == 2  # still key-1 and key-2 -- no new row was inserted
    finally:
        await engine.dispose()
