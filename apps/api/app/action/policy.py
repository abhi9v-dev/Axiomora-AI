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
# that -- see app.api.actions's confirmation-dialog note). Power BI push
# rows and dataset refresh are feature-flagged behind POWER_BI_ENABLED
# (see _allowed_action_types below); "replace dataset/report" has no entry
# here at all, since the table marks it "Prohibited in MVP" rather than
# feature-flagged -- it is always rejected, flag or no flag.
_ALWAYS_ALLOWED_ACTION_TYPES: frozenset[ActionType] = frozenset({"export_excel"})
_POWER_BI_FLAGGED_ACTION_TYPES: frozenset[ActionType] = frozenset(
    {"power_bi_push", "power_bi_refresh"}
)
POWER_BI_PROHIBITED_ACTION_TYPES: frozenset[ActionType] = frozenset({"power_bi_replace"})

# docs/07's table: Power BI destinations need "Analyst confirmation" /
# "Analyst/admin confirmation", distinct from Excel's "result owner" user
# click. No auth/user-identity system exists in this project (no roadmap
# phase adds one -- see docs/progress.md's Phase 7 known limitations for
# the same caveat about "result_owner"), so this is a documented
# placeholder identity, not a real approver lookup.
POWER_BI_APPROVER_PLACEHOLDER = "analyst"
EXCEL_APPROVER_PLACEHOLDER = "result_owner"


@dataclass
class ActionPolicyResult:
    ok: bool
    destination: str
    reason: str | None = None


def evaluate_action_policy(
    snapshot: RunSnapshot, action_type: ActionType, *, power_bi_enabled: bool = False
) -> ActionPolicyResult:
    if action_type in POWER_BI_PROHIBITED_ACTION_TYPES:
        return ActionPolicyResult(
            ok=False,
            destination="none",
            reason=f"Action type '{action_type}' is prohibited and will not be implemented.",
        )

    allowed_types = _ALWAYS_ALLOWED_ACTION_TYPES | (
        _POWER_BI_FLAGGED_ACTION_TYPES if power_bi_enabled else frozenset()
    )
    if action_type not in allowed_types:
        if action_type in _POWER_BI_FLAGGED_ACTION_TYPES:
            reason = (
                f"The Power BI adapter is disabled (POWER_BI_ENABLED=false) for '{action_type}'."
            )
        else:
            reason = f"Action type '{action_type}' is not available yet."
        return ActionPolicyResult(ok=False, destination="none", reason=reason)

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

    if action_type == "export_excel":
        return ActionPolicyResult(ok=True, destination="download")
    return ActionPolicyResult(
        ok=True, destination=f"power_bi:{action_type.removeprefix('power_bi_')}"
    )
