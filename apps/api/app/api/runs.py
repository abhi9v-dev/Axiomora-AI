"""The runs API (docs/06_DATA_MODEL_API_CONTRACTS.md's Public API table):
start a question run, fetch its full state, stream its progress, answer a
clarification and cancel it.

POST /runs and POST /runs/{id}/clarification both do their fast, request-
scoped work inline (create/validate + persist + publish one event) and then
schedule the actual pipeline run (app.orchestrator.service.execute_run) as
a background asyncio task with its own session/engine/providers, so the
endpoint can return immediately rather than blocking on however long
retrieval + NL2SQL + validation + insight generation takes. Progress is
observed by connecting to GET /runs/{id}/events, not by waiting on the
POST response.

Only one demo source/tenant exists yet (no multi-tenant auth in this
project -- see docs/10_IMPLEMENTATION_ROADMAP.md's phase list, which has no
auth phase): DEFAULT_TENANT_ID/DEFAULT_SOURCE_ID match the catalog
documents actually ingested (data/glossary/*.yaml) and the warehouse
actually seeded (app.db.seed) so a run always has real context and data to
work against.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_orchestrator_params, get_session
from app.config import get_settings
from app.db.session import get_engine, get_warehouse_engine
from app.embeddings.factory import get_embedding_provider
from app.llm.factory import get_llm_provider
from app.orchestrator.events import get_event_bus
from app.orchestrator.schema import RunSnapshot, RunStatus, RunSummary
from app.orchestrator.service import (
    NotAwaitingClarificationError,
    OrchestratorParams,
    cancel_run,
    create_run,
    execute_run,
    record_clarification,
)
from app.orchestrator.store import get_run, list_runs

router = APIRouter(prefix="/api/v1", tags=["runs"])

DEFAULT_TENANT_ID = "default"
DEFAULT_SOURCE_ID = "marketplace_demo"

# run_id -> the background task executing it, so POST /cancel can actually
# interrupt it. Process-local, same single-process assumption as
# app.orchestrator.events's bus registry.
_TASKS: dict[uuid.UUID, asyncio.Task[None]] = {}


class StartRunRequest(BaseModel):
    question: str
    source_id: str = DEFAULT_SOURCE_ID
    # Accepted per docs/06_DATA_MODEL_API_CONTRACTS.md's start-run request
    # contract; not yet applied anywhere (no relative-date/timezone handling
    # exists in the NL2SQL agent yet, e.g. for "last quarter").
    timezone: str | None = None


class ClarificationRequest(BaseModel):
    answer: str


class RunAcceptedResponse(BaseModel):
    run_id: uuid.UUID
    status: RunStatus


async def _execute_in_background(
    snapshot: RunSnapshot, effective_question: str, params: OrchestratorParams
) -> None:
    settings = get_settings()
    session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    warehouse_engine = get_warehouse_engine()
    llm_provider = get_llm_provider(settings)
    embedding_provider = get_embedding_provider(settings)
    bus = get_event_bus(snapshot.run_id)

    try:
        async with session_factory() as session:
            await execute_run(
                session=session,
                engine=warehouse_engine,
                llm_provider=llm_provider,
                embedding_provider=embedding_provider,
                bus=bus,
                snapshot=snapshot,
                effective_question=effective_question,
                params=params,
            )
    except asyncio.CancelledError:
        async with session_factory() as session:
            await cancel_run(session, snapshot.run_id)
        raise


def _schedule_execution(
    snapshot: RunSnapshot, effective_question: str, params: OrchestratorParams
) -> None:
    task = asyncio.create_task(_execute_in_background(snapshot, effective_question, params))
    _TASKS[snapshot.run_id] = task
    task.add_done_callback(lambda _: _TASKS.pop(snapshot.run_id, None))


@router.post("/runs", status_code=202, response_model=RunAcceptedResponse)
async def start_run_endpoint(
    body: StartRunRequest,
    session: AsyncSession = Depends(get_session),
    params: OrchestratorParams = Depends(get_orchestrator_params),
) -> RunAcceptedResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question must not be empty")

    snapshot = await create_run(
        session=session,
        tenant_id=DEFAULT_TENANT_ID,
        source_id=body.source_id or DEFAULT_SOURCE_ID,
        question=question,
    )
    _schedule_execution(snapshot, question, params)
    return RunAcceptedResponse(run_id=snapshot.run_id, status=snapshot.status)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RunSummary]:
    return await list_runs(session, tenant_id=DEFAULT_TENANT_ID, limit=limit)


@router.get("/runs/{run_id}", response_model=RunSnapshot)
async def get_run_endpoint(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RunSnapshot:
    snapshot = await get_run(session, run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snapshot


@router.get("/runs/{run_id}/events")
async def run_events_endpoint(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    existing = await get_run(session, run_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="run not found")

    bus = get_event_bus(run_id)

    async def event_stream() -> AsyncIterator[str]:
        async for snapshot in bus.subscribe():
            yield f"event: run_update\ndata: {snapshot.model_dump_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/clarification", status_code=202, response_model=RunAcceptedResponse)
async def submit_clarification_endpoint(
    run_id: uuid.UUID,
    body: ClarificationRequest,
    session: AsyncSession = Depends(get_session),
    params: OrchestratorParams = Depends(get_orchestrator_params),
) -> RunAcceptedResponse:
    answer = body.answer.strip()
    if not answer:
        raise HTTPException(status_code=422, detail="answer must not be empty")

    try:
        snapshot, effective_question = await record_clarification(
            session=session, run_id=run_id, answer=answer
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="run not found") from None
    except NotAwaitingClarificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _schedule_execution(snapshot, effective_question, params)
    return RunAcceptedResponse(run_id=run_id, status=snapshot.status)


@router.post("/runs/{run_id}/cancel", response_model=RunSnapshot)
async def cancel_run_endpoint(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RunSnapshot:
    task = _TASKS.get(run_id)
    if task is not None:
        task.cancel()

    snapshot = await cancel_run(session, run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snapshot
