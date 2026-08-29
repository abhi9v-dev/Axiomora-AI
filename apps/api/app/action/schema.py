"""Versioned Action contracts (docs/06_DATA_MODEL_API_CONTRACTS.md's
`action` entity: id, run_id, type, destination, status, idempotency_key,
approved_by).

`export_excel` was the only implemented action type in Phase 7.
`power_bi_push` and `power_bi_refresh` (docs/07_SECURITY_GOVERNANCE.md's
action policy table: "create Power BI push rows", "trigger dataset
refresh") become available in Phase 8 once `POWER_BI_ENABLED=true`
(app.action.policy). `power_bi_replace` ("replace dataset/report") stays
permanently rejected -- the table marks it "Prohibited in MVP", not
feature-flagged, so no adapter method or execution path exists for it at
all.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel

ActionType = Literal["export_excel", "power_bi_push", "power_bi_refresh", "power_bi_replace"]
# "failed" is distinct from "rejected": a rejection is a stable policy
# decision (repeating the same idempotency key always returns the same
# rejection); a failure is an external adapter error after policy already
# approved the request, so docs/03_ARCHITECTURE.md's failure-handling rule
# ("action failure: retain validated answer and an idempotency key for
# safe retry") applies -- app.api.actions re-attempts execution, rather
# than replaying a cached outcome, when it sees a "failed" row for the
# same key.
ActionStatus = Literal["completed", "rejected", "failed"]


class ActionRequest(BaseModel):
    type: ActionType
    idempotency_key: str


class ActionRecord(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    type: ActionType
    destination: str
    status: ActionStatus
    idempotency_key: str
    approved_by: str | None
    # Rejection reason when status="rejected"; adapter error message when
    # status="failed"; a human-readable outcome receipt (e.g. "Pushed 42
    # rows...") when status="completed" for a power_bi_* action, so an
    # idempotent replay can return the original receipt without re-calling
    # the adapter. Always None for a completed export_excel, since that
    # workbook is regenerated fresh from the run snapshot on every replay.
    rejection_reason: str | None
    created_at: dt.datetime
