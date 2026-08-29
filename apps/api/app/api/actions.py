"""The actions API (docs/06_DATA_MODEL_API_CONTRACTS.md's Public API
table): `POST /api/v1/runs/{run_id}/actions` -- request export/publish.

One endpoint handles both "create" and "idempotent replay" in a single
POST, mirroring a standard Idempotency-Key REST pattern: repeating the
same request with the same `idempotency_key` returns the same outcome
again rather than performing the action twice
(docs/07_SECURITY_GOVERNANCE.md: "action requests use idempotency keys").
For `export_excel` (the only implemented action type -- Phase 7's scope;
every Power BI destination is feature-flagged/prohibited until Phase 8),
the response body *is* the workbook itself, generated fresh from the
run's already-validated, immutable snapshot every time -- never written
to disk (docs/09_DEPLOYMENT_OPERATIONS.md: "Excel files generated on
demand and downloaded immediately"), so a repeat download for the same
key is simply regenerated rather than re-served from a cache.

A confirmation is expected to happen before this endpoint is ever called
(the Ask page's ActionDialog shows destination, data timestamp and effect
first, per docs/07's "the confirmation dialog must identify destination,
effect, data timestamp and whether existing content changes") -- this
endpoint is the click-through action itself.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.action.policy import evaluate_action_policy
from app.action.schema import ActionRecord, ActionRequest
from app.action.store import get_action_by_idempotency_key, record_action
from app.action.workbook import build_workbook
from app.api.deps import get_session
from app.orchestrator.schema import RunSnapshot
from app.orchestrator.store import get_run

router = APIRouter(prefix="/api/v1", tags=["actions"])

_EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _filename(run_id: uuid.UUID) -> str:
    return f"bi-copilot-run-{run_id}.xlsx"


def _action_response(snapshot: RunSnapshot, record: ActionRecord) -> Response:
    if record.type == "export_excel":
        content = build_workbook(snapshot)
        return Response(
            content=content,
            media_type=_EXCEL_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{_filename(snapshot.run_id)}"',
                "X-Action-Id": str(record.id),
            },
        )
    # Unreachable while ALLOWED_ACTION_TYPES is export_excel-only -- a
    # request for anything else is always rejected before reaching here.
    raise HTTPException(status_code=501, detail=f"No handler for action type '{record.type}'.")


@router.post("/runs/{run_id}/actions")
async def request_action_endpoint(
    run_id: uuid.UUID,
    body: ActionRequest,
    session: AsyncSession = Depends(get_session),
) -> Response:
    idempotency_key = body.idempotency_key.strip()
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="idempotency_key must not be empty")

    snapshot = await get_run(session, run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")

    existing = await get_action_by_idempotency_key(session, run_id, idempotency_key)
    if existing is not None:
        if existing.status == "rejected":
            raise HTTPException(status_code=403, detail=existing.rejection_reason)
        return _action_response(snapshot, existing)

    policy = evaluate_action_policy(snapshot, body.type)
    record = ActionRecord(
        id=uuid.uuid4(),
        run_id=run_id,
        type=body.type,
        destination=policy.destination,
        status="completed" if policy.ok else "rejected",
        idempotency_key=idempotency_key,
        approved_by="result_owner" if policy.ok else None,
        rejection_reason=None if policy.ok else policy.reason,
        created_at=dt.datetime.now(dt.UTC),
    )

    try:
        await record_action(session, record)
    except IntegrityError:
        # Lost a race with a concurrent request using the same key -- the
        # other request's row won; treat this one as the same idempotent
        # replay rather than surfacing a spurious server error.
        await session.rollback()
        existing = await get_action_by_idempotency_key(session, run_id, idempotency_key)
        assert existing is not None
        record = existing

    if record.status == "rejected":
        raise HTTPException(status_code=403, detail=record.rejection_reason)

    return _action_response(snapshot, record)
