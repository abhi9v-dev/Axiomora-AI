"""Action policy (docs/07_SECURITY_GOVERNANCE.md's action policy table).

Checked before any action is recorded or executed -- CLAUDE.md's
architecture invariant "external actions require policy checks, explicit
user approval and idempotency keys" and the SRS's forbidden Action-agent
behavior, "acting without policy and approval checks". A rejected request
is still recorded (app.action.store), matching docs/07's audit-events
requirement to capture "action approvals and outcomes" -- rejection is an
outcome, not a non-event.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.action.schema import ActionType
from app.orchestrator.schema import RunSnapshot

# docs/07's action policy table: Excel download is allowed for the result
# owner with just a user click (no destination-specific approval beyond
# that -- see app.api.actions's confirmation-dialog note). Every Power BI
# destination is feature-flagged/prohibited and simply doesn't exist yet
# (Phase 8) -- rejected with a specific reason rather than a generic 422.
ALLOWED_ACTION_TYPES: frozenset[ActionType] = frozenset({"export_excel"})


@dataclass
class ActionPolicyResult:
    ok: bool
    destination: str
    reason: str | None = None


def evaluate_action_policy(snapshot: RunSnapshot, action_type: ActionType) -> ActionPolicyResult:
    if action_type not in ALLOWED_ACTION_TYPES:
        return ActionPolicyResult(
            ok=False,
            destination="none",
            reason=f"Action type '{action_type}' is not available yet.",
        )

    if snapshot.status != "READY":
        return ActionPolicyResult(
            ok=False,
            destination="none",
            reason=f"The run has not reached a validated, ready answer (status={snapshot.status}).",
        )

    latest_attempt = snapshot.attempts[-1] if snapshot.attempts else None
    if (
        latest_attempt is None
        or latest_attempt.validator.status != "pass"
        or latest_attempt.validator.result is None
    ):
        return ActionPolicyResult(
            ok=False, destination="none", reason="No validated result is available for this run."
        )

    return ActionPolicyResult(ok=True, destination="download")
