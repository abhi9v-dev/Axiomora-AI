"""app.action.policy.evaluate_action_policy -- pure Python, no database
needed. Mirrors the adversarial-but-simple style of
test_validator_policy.py: each test is one clear policy decision."""

from __future__ import annotations

import datetime as dt
import uuid

from app.action.policy import evaluate_action_policy
from app.insight.schema import InsightOutput
from app.nl2sql.schema import NL2SQLOutput
from app.orchestrator.schema import AttemptRecord, RunSnapshot
from app.validator.schema import QueryResult, ValidationCheck, ValidatorOutput

_NOW = dt.datetime.now(dt.UTC)


def _nl2sql() -> NL2SQLOutput:
    return NL2SQLOutput(sql="SELECT 1", dialect="postgres", confidence=0.9)


def _passing_validator() -> ValidatorOutput:
    return ValidatorOutput(
        status="pass",
        checks=[ValidationCheck(name="sql_policy", status="pass", details="ok")],
        repairable=False,
        result=QueryResult(columns=["x"], rows=[[1]], row_count=1, truncated=False),
    )


def _failing_validator() -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="sql_policy", status="fail", details="bad")],
        repairable=False,
        feedback="bad",
    )


def _snapshot(*, status: str = "READY", attempts: list[AttemptRecord] | None = None) -> RunSnapshot:
    return RunSnapshot(
        run_id=uuid.uuid4(),
        tenant_id="default",
        source_id="marketplace_demo",
        question="Why did hold time spike?",
        status=status,
        attempts=attempts if attempts is not None else [],
        insight=InsightOutput(headline="h", narrative="n"),
        created_at=_NOW,
        updated_at=_NOW,
        completed_at=_NOW,
    )


def test_ready_run_with_a_passing_result_is_allowed() -> None:
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_passing_validator())]
    )

    result = evaluate_action_policy(snapshot, "export_excel")

    assert result.ok
    assert result.destination == "download"
    assert result.reason is None


def test_a_power_bi_action_is_rejected_when_the_flag_is_disabled() -> None:
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_passing_validator())]
    )

    result = evaluate_action_policy(snapshot, "power_bi_push", power_bi_enabled=False)

    assert not result.ok
    assert result.reason is not None and "disabled" in result.reason


def test_a_power_bi_push_is_allowed_once_the_flag_is_enabled() -> None:
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_passing_validator())]
    )

    result = evaluate_action_policy(snapshot, "power_bi_push", power_bi_enabled=True)

    assert result.ok
    assert result.destination == "power_bi:push"


def test_a_power_bi_refresh_is_allowed_once_the_flag_is_enabled() -> None:
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_passing_validator())]
    )

    result = evaluate_action_policy(snapshot, "power_bi_refresh", power_bi_enabled=True)

    assert result.ok
    assert result.destination == "power_bi:refresh"


def test_power_bi_replace_is_always_rejected_even_with_the_flag_enabled() -> None:
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_passing_validator())]
    )

    result = evaluate_action_policy(snapshot, "power_bi_replace", power_bi_enabled=True)

    assert not result.ok
    assert result.reason is not None and "prohibited" in result.reason


def test_power_bi_push_still_requires_a_ready_validated_run_when_flag_enabled() -> None:
    snapshot = _snapshot(status="GENERATING_SQL", attempts=[])

    result = evaluate_action_policy(snapshot, "power_bi_push", power_bi_enabled=True)

    assert not result.ok
    assert result.reason is not None and "GENERATING_SQL" in result.reason


def test_a_run_still_in_progress_is_rejected() -> None:
    snapshot = _snapshot(status="GENERATING_SQL", attempts=[])

    result = evaluate_action_policy(snapshot, "export_excel")

    assert not result.ok
    assert result.reason is not None and "GENERATING_SQL" in result.reason


def test_a_failed_run_is_rejected_even_if_marked_ready_somehow() -> None:
    # Defense in depth: even if status drifted, a failing/absent validated
    # result must still block the action (CLAUDE.md: "failed validation
    # blocks... the Action Agent").
    snapshot = _snapshot(
        attempts=[AttemptRecord(attempt_no=1, nl2sql=_nl2sql(), validator=_failing_validator())]
    )

    result = evaluate_action_policy(snapshot, "export_excel")

    assert not result.ok
    assert result.reason is not None and "No validated result" in result.reason


def test_a_ready_run_with_no_attempts_is_rejected() -> None:
    snapshot = _snapshot(attempts=[])

    result = evaluate_action_policy(snapshot, "export_excel")

    assert not result.ok
