"""Versioned Action contracts (docs/06_DATA_MODEL_API_CONTRACTS.md's
`action` entity: id, run_id, type, destination, status, idempotency_key,
approved_by).

Only `export_excel` exists in Phase 7 -- the Power BI destinations
(docs/07_SECURITY_GOVERNANCE.md's action policy table: "create Power BI
push rows", "trigger dataset refresh", "replace dataset/report") are
Phase 8 scope, feature-flagged behind `POWER_BI_ENABLED`. Listing them
here as not-yet-implemented, rather than only ever accepting
"export_excel", is what lets app.action.policy give a real "not available
yet" reason instead of a generic validation error when someone requests
one early.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel

ActionType = Literal["export_excel", "power_bi_push", "power_bi_refresh", "power_bi_replace"]
ActionStatus = Literal["completed", "rejected"]


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
    rejection_reason: str | None
    created_at: dt.datetime
