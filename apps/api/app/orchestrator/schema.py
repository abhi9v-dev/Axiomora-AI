"""The orchestrator's run-state contract (docs/03_ARCHITECTURE.md's
Orchestration state diagram; docs/06_DATA_MODEL_API_CONTRACTS.md's `run`
entity and `GET /api/v1/runs/{run_id}` -- "get full safe run state").

`RunSnapshot` is the single shape returned by GET /runs/{run_id}, streamed
over SSE on every state transition, and persisted (as JSON) in
`runs.run` -- one version-controlled contract for all three, so the API
response, the live stream and the stored row can never drift from each
other.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.catalog.schema import RetrievalResult
from app.insight.schema import InsightOutput
from app.nl2sql.schema import NL2SQLOutput
from app.validator.schema import ValidatorOutput

# Mirrors docs/03_ARCHITECTURE.md's state diagram, minus the ACTION_* states
# (Phase 7's Action Agent doesn't exist yet) and collapsed to what
# app.validator.agent.validate_and_execute actually observes as one atomic
# call: STATIC_VALIDATION / EXECUTING / RESULT_VALIDATION together become
# VALIDATING, since Phase 4 never exposed those as independently observable
# steps.
RunStatus = Literal[
    "RECEIVED",
    "RETRIEVING",
    "GENERATING_SQL",
    "VALIDATING",
    "REPAIR_SQL",
    "GENERATING_INSIGHT",
    "READY",
    "NEEDS_CLARIFICATION",
    "FAILED",
    "CANCELLED",
]

TERMINAL_STATUSES: frozenset[RunStatus] = frozenset(
    {"READY", "NEEDS_CLARIFICATION", "FAILED", "CANCELLED"}
)


class AttemptRecord(BaseModel):
    """One NL2SQL-generate + validate round trip, in the order attempted --
    the full repair history, not just the winning attempt, so the Evidence
    & SQL panel can show why earlier attempts were rejected."""

    attempt_no: int
    nl2sql: NL2SQLOutput
    validator: ValidatorOutput


class RunSnapshot(BaseModel):
    run_id: uuid.UUID
    tenant_id: str
    source_id: str
    question: str
    status: RunStatus

    retrieved_context: list[RetrievalResult] = Field(default_factory=list)
    attempts: list[AttemptRecord] = Field(default_factory=list)
    insight: InsightOutput | None = None
    insight_error: str | None = None

    clarification_question: str | None = None
    clarification_options: list[str] | None = None
    clarification_answer: str | None = None

    error: str | None = None

    created_at: dt.datetime
    updated_at: dt.datetime
    completed_at: dt.datetime | None = None


class RunSummary(BaseModel):
    """The compact shape GET /api/v1/runs (history) returns -- enough for
    RunHistory to render a list without pulling every run's full nested
    state."""

    run_id: uuid.UUID
    question: str
    status: RunStatus
    created_at: dt.datetime
