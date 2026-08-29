"""Persistence for ActionRecord, against `runs.action` (app.db.action_models.Action).

Every read and write goes through ActionRecord -- callers never see the
ORM row, matching app.orchestrator.store's convention for `runs.run`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.action.schema import ActionRecord
from app.db.action_models import Action


def _to_record(row: Action) -> ActionRecord:
    return ActionRecord(
        id=row.id,
        run_id=row.run_id,
        type=row.type,
        destination=row.destination,
        status=row.status,
        idempotency_key=row.idempotency_key,
        approved_by=row.approved_by,
        rejection_reason=row.rejection_reason,
        created_at=row.created_at,
    )


async def get_action_by_idempotency_key(
    session: AsyncSession, run_id: uuid.UUID, idempotency_key: str
) -> ActionRecord | None:
    row = await session.scalar(
        select(Action).where(Action.run_id == run_id, Action.idempotency_key == idempotency_key)
    )
    return _to_record(row) if row is not None else None


async def record_action(
    session: AsyncSession,
    record: ActionRecord,
) -> ActionRecord:
    row = Action(
        id=record.id,
        run_id=record.run_id,
        type=record.type,
        destination=record.destination,
        status=record.status,
        idempotency_key=record.idempotency_key,
        approved_by=record.approved_by,
        rejection_reason=record.rejection_reason,
        created_at=record.created_at,
    )
    session.add(row)
    await session.commit()
    return record


async def list_actions(session: AsyncSession, run_id: uuid.UUID) -> list[ActionRecord]:
    rows = (
        await session.scalars(
            select(Action).where(Action.run_id == run_id).order_by(Action.created_at)
        )
    ).all()
    return [_to_record(row) for row in rows]
