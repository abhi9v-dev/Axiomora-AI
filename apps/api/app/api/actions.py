"""The actions API (docs/06_DATA_MODEL_API_CONTRACTS.md's Public API
table): `POST /api/v1/runs/{run_id}/actions` -- request export/publish.

One endpoint handles both "create" and "idempotent replay" in a single
POST, mirroring a standard Idempotency-Key REST pattern: repeating the
same request with the same `idempotency_key` returns the same outcome
again rather than performing the action twice
(docs/07_SECURITY_GOVERNANCE.md: "action requests use idempotency keys").
For `export_excel`, the response body *is* the workbook itself, generated
fresh from the run's already-validated, immutable snapshot every time --
never written to disk (docs/09_DEPLOYMENT_OPERATIONS.md: "Excel files
generated on demand and downloaded immediately"). For `power_bi_push`/
`power_bi_refresh` (Phase 8, feature-flagged behind `POWER_BI_ENABLED`),
the response body is a small JSON receipt instead, since there is no file
to download.

The idempotency row is inserted *before* the action actually executes
(status optimistically "completed", corrected afterward if it fails) --
whichever concurrent request wins the database's unique-constraint race
is the only one that ever calls the Power BI adapter or builds a
workbook; the loser replays the winner's outcome. This matters
specifically for Power BI: unlike Excel generation (pure, side-effect-free,
safe to compute redundantly), pushing rows or triggering a refresh is a
real external side effect that must not happen twice for one logical
request.

A confirmation is expected to happen before this endpoint is ever called
(the Ask page's ActionDialog shows destination, data timestamp and effect
first, per docs/07's "the confirmation dialog must identify destination,
effect, data timestamp and whether existing content changes") -- this
endpoint is the click-through action itself.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.action.policy import (
    EXCEL_APPROVER_PLACEHOLDER,
    POWER_BI_APPROVER_PLACEHOLDER,
    evaluate_action_policy,
)
from app.action.power_bi.base import PowerBIAdapter
from app.action.power_bi.errors import PowerBIAdapterError
from app.action.schema import ActionRecord, ActionRequest, ActionType
from app.action.store import (
    get_action_by_idempotency_key,
    record_action,
    update_action_outcome,
)
from app.action.workbook import build_workbook
from app.api.deps import get_power_bi_adapter_dep, get_session, get_settings_dep
from app.config import Settings
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
    if record.status == "completed":
        payload = {
            "action_id": str(record.id),
            "type": record.type,
            "status": record.status,
            "destination": record.destination,
            "detail": record.rejection_reason,
        }
        return Response(
            content=json.dumps(payload),
            media_type="application/json",
            headers={"X-Action-Id": str(record.id)},
        )
    # Unreachable given the endpoint's own control flow -- a rejected or
    # failed record is always turned into an HTTPException before reaching
    # here, never passed to this function.
    raise AssertionError(f"_action_response called with a non-completed record: {record.status}")


async def _record_or_get_winner(
    session: AsyncSession, run_id: uuid.UUID, idempotency_key: str, candidate: ActionRecord
) -> ActionRecord:
    """Attempts to insert `candidate`; if a concurrent request already
    claimed the same (run_id, idempotency_key), returns that winning row
    instead -- the caller must never act (call an adapter, etc.) on behalf
    of a candidate it did not actually win."""
    try:
        return await record_action(session, candidate)
    except IntegrityError:
        await session.rollback()
        winner = await get_action_by_idempotency_key(session, run_id, idempotency_key)
        assert winner is not None
        return winner


def _raise_for_non_completed(record: ActionRecord) -> None:
    if record.status == "rejected":
        raise HTTPException(status_code=403, detail=record.rejection_reason)
    if record.status == "failed":
        raise HTTPException(status_code=502, detail=record.rejection_reason)


async def _run_power_bi_action(
    action_type: ActionType,
    snapshot: RunSnapshot,
    adapter: PowerBIAdapter,
    settings: Settings,
) -> str:
    """Executes a power_bi_* action for real (or against the mock adapter)
    and returns a human-readable receipt describing what happened, stored
    so a later idempotent replay never needs to call the adapter again."""
    if action_type == "power_bi_push":
        latest_attempt = snapshot.attempts[-1]
        result_data = latest_attempt.validator.result
        assert result_data is not None
        rows = [dict(zip(result_data.columns, row, strict=True)) for row in result_data.rows]
        push_result = await adapter.push_rows(
            dataset_id=settings.POWER_BI_DATASET_ID,
            table_name=settings.POWER_BI_TABLE_NAME,
            rows=rows,
        )
        return (
            f"Pushed {push_result.rows_pushed} row(s) to Power BI dataset "
            f"'{push_result.dataset_id}', table '{push_result.table_name}'."
        )
    if action_type == "power_bi_refresh":
        refresh_result = await adapter.refresh_dataset(dataset_id=settings.POWER_BI_DATASET_ID)
        return (
            f"Triggered a refresh of Power BI dataset '{refresh_result.dataset_id}' "
            f"(refresh id {refresh_result.refresh_request_id})."
        )
    raise AssertionError(f"{action_type!r} is not a Power BI action")


@router.post("/runs/{run_id}/actions")
async def request_action_endpoint(
    run_id: uuid.UUID,
    body: ActionRequest,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    power_bi_adapter: PowerBIAdapter = Depends(get_power_bi_adapter_dep),
) -> Response:
    idempotency_key = body.idempotency_key.strip()
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="idempotency_key must not be empty")

    snapshot = await get_run(session, run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")

    existing = await get_action_by_idempotency_key(session, run_id, idempotency_key)

    if existing is not None and existing.status != "failed":
        _raise_for_non_completed(existing)
        return _action_response(snapshot, existing)

    if existing is None:
        policy = evaluate_action_policy(
            snapshot, body.type, power_bi_enabled=settings.POWER_BI_ENABLED
        )
        if not policy.ok:
            rejected = ActionRecord(
                id=uuid.uuid4(),
                run_id=run_id,
                type=body.type,
                destination=policy.destination,
                status="rejected",
                idempotency_key=idempotency_key,
                approved_by=None,
                rejection_reason=policy.reason,
                created_at=dt.datetime.now(dt.UTC),
            )
            winner = await _record_or_get_winner(session, run_id, idempotency_key, rejected)
            _raise_for_non_completed(winner)
            return _action_response(snapshot, winner)

        approved_by = (
            EXCEL_APPROVER_PLACEHOLDER
            if body.type == "export_excel"
            else POWER_BI_APPROVER_PLACEHOLDER
        )
        claim = ActionRecord(
            id=uuid.uuid4(),
            run_id=run_id,
            type=body.type,
            destination=policy.destination,
            status="completed",
            idempotency_key=idempotency_key,
            approved_by=approved_by,
            rejection_reason=None,
            created_at=dt.datetime.now(dt.UTC),
        )
        winner = await _record_or_get_winner(session, run_id, idempotency_key, claim)
        if winner.id != claim.id:
            # Lost the race to claim this idempotency key: another request
            # already executed (or is executing) it. Never call the
            # adapter/build a workbook ourselves in this branch.
            _raise_for_non_completed(winner)
            return _action_response(snapshot, winner)
        pending = claim
    else:
        # existing.status == "failed": retry using the already-claimed row
        # (docs/03_ARCHITECTURE.md: "action failure: retain validated
        # answer and an idempotency key for safe retry").
        pending = existing

    if pending.type == "export_excel":
        return _action_response(snapshot, pending)

    try:
        detail = await _run_power_bi_action(pending.type, snapshot, power_bi_adapter, settings)
    except PowerBIAdapterError as exc:
        await update_action_outcome(session, pending.id, status="failed", rejection_reason=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    finalized = await update_action_outcome(
        session, pending.id, status="completed", rejection_reason=detail
    )
    return _action_response(snapshot, finalized)
