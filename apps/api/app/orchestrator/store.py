"""Persistence for RunSnapshot, against `runs.run` (app.db.run_models.Run).

Every read and write goes through RunSnapshot -- callers never see the ORM
row or raw JSONB, matching the rest of the codebase's "typed contracts
only" convention (see app.catalog.retrieval / app.validator.executor for
the same pattern against other tables).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.schema import RetrievalResult
from app.db.run_models import Run
from app.insight.schema import InsightOutput
from app.orchestrator.schema import AttemptRecord, RunSnapshot, RunSummary


def _apply_snapshot(row: Run, snapshot: RunSnapshot) -> None:
    row.id = snapshot.run_id
    row.tenant_id = snapshot.tenant_id
    row.source_id = snapshot.source_id
    row.question = snapshot.question
    row.status = snapshot.status
    row.retrieved_context = [item.model_dump(mode="json") for item in snapshot.retrieved_context]
    row.attempts = [item.model_dump(mode="json") for item in snapshot.attempts]
    row.insight = snapshot.insight.model_dump(mode="json") if snapshot.insight else None
    row.insight_error = snapshot.insight_error
    row.clarification_question = snapshot.clarification_question
    row.clarification_options = snapshot.clarification_options
    row.clarification_answer = snapshot.clarification_answer
    row.error = snapshot.error
    row.created_at = snapshot.created_at
    row.updated_at = snapshot.updated_at
    row.completed_at = snapshot.completed_at


def _to_snapshot(row: Run) -> RunSnapshot:
    return RunSnapshot(
        run_id=row.id,
        tenant_id=row.tenant_id,
        source_id=row.source_id,
        question=row.question,
        status=row.status,
        retrieved_context=[RetrievalResult.model_validate(item) for item in row.retrieved_context],
        attempts=[AttemptRecord.model_validate(item) for item in row.attempts],
        insight=InsightOutput.model_validate(row.insight) if row.insight else None,
        insight_error=row.insight_error,
        clarification_question=row.clarification_question,
        clarification_options=row.clarification_options,
        clarification_answer=row.clarification_answer,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


async def create_run(session: AsyncSession, snapshot: RunSnapshot) -> None:
    row = Run()
    _apply_snapshot(row, snapshot)
    session.add(row)
    await session.commit()


async def save_run(session: AsyncSession, snapshot: RunSnapshot) -> None:
    row = await session.get(Run, snapshot.run_id)
    if row is None:
        raise LookupError(f"No run {snapshot.run_id} to update.")
    _apply_snapshot(row, snapshot)
    await session.commit()


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> RunSnapshot | None:
    row = await session.get(Run, run_id)
    return _to_snapshot(row) if row is not None else None


async def list_runs(session: AsyncSession, *, tenant_id: str, limit: int) -> list[RunSummary]:
    stmt = (
        select(Run).where(Run.tenant_id == tenant_id).order_by(Run.created_at.desc()).limit(limit)
    )
    rows = (await session.scalars(stmt)).all()
    return [
        RunSummary(
            run_id=row.id, question=row.question, status=row.status, created_at=row.created_at
        )
        for row in rows
    ]
