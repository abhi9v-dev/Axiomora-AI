"""The Validator Agent: parses, policy-checks and (if safe) executes
NL2SQL's draft SQL against the read-only warehouse, then checks the shape
of the result.

Never calls back into NL2SQL itself -- that coordination (the bounded
repair loop) is app.pipeline's job; this agent only validates what it's
given and reports repair feedback for the caller to act on. Forbidden
behavior (docs/02_SRS_SRD.md): editing data, or silently accepting
failures.
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.nl2sql.schema import NL2SQLOutput
from app.validator.executor import execute_readonly
from app.validator.policy import validate_sql_policy
from app.validator.result_checks import (
    check_comparison_period_completeness,
    check_non_negative_columns,
    check_not_empty,
    check_not_truncated,
)
from app.validator.schema import ValidationCheck, ValidatorOutput

# Warehouse columns that can never legitimately be negative -- mirrors
# data/glossary/validation_rules.yaml's hold_hours_non_negative rule.
DEFAULT_NON_NEGATIVE_COLUMNS = frozenset(
    {
        "claim_wait_hrs",
        "start_delay_hrs",
        "working_time_hrs",
        "assignee_hold_hrs",
        "total_duration_hrs",
        "median_hold_hrs",
        "open_age_hrs",
        "unclaimed_age_hrs",
        "project_age_days",
        "days_since_last_activity",
        "task_count",
        "open_task_count",
        "unclaimed_task_count",
    }
)


def _policy_failure(violations: list[str]) -> ValidatorOutput:
    return ValidatorOutput(
        status="fail",
        checks=[ValidationCheck(name="sql_policy", status="fail", details=v) for v in violations],
        repairable=True,
        feedback=(
            "The generated SQL violated the safety policy: "
            + "; ".join(violations)
            + ". Regenerate using only the approved tables/views and functions."
        ),
    )


async def validate_and_execute(
    engine: AsyncEngine,
    nl2sql_output: NL2SQLOutput,
    *,
    timeout_ms: int,
    row_limit: int,
    non_negative_columns: frozenset[str] = DEFAULT_NON_NEGATIVE_COLUMNS,
) -> ValidatorOutput:
    policy = validate_sql_policy(nl2sql_output.sql)
    if not policy.ok:
        return _policy_failure(policy.violations)

    missing_params = sorted(policy.placeholders - set(nl2sql_output.parameters.keys()))
    if missing_params:
        names = ", ".join(missing_params)
        return _policy_failure(
            [f"SQL references parameter(s) {names} with no matching value in `parameters`."]
        )

    assert policy.normalized_sql is not None  # guaranteed by policy.ok

    try:
        result = await execute_readonly(
            engine,
            policy.normalized_sql,
            dict(nl2sql_output.parameters),
            timeout_ms=timeout_ms,
            row_limit=row_limit,
        )
    except SQLAlchemyError as exc:
        return ValidatorOutput(
            status="fail",
            checks=[ValidationCheck(name="execution", status="fail", details=str(exc))],
            repairable=True,
            feedback=(
                f"Execution against the warehouse failed: {exc}. Simplify the query, narrow "
                "the filters, or reduce the aggregation scope and try again."
            ),
        )

    checks: list[ValidationCheck] = [
        ValidationCheck(
            name="sql_policy", status="pass", details="Approved objects and functions only."
        ),
        check_not_empty(result),
        check_not_truncated(result, row_limit=row_limit),
        check_non_negative_columns(result, non_negative_columns=non_negative_columns),
    ]
    period_check = check_comparison_period_completeness(result)
    if period_check is not None:
        checks.append(period_check)

    hard_failures = [c for c in checks if c.status == "fail"]
    if hard_failures:
        feedback = (
            "The query executed but failed a result check: "
            + "; ".join(c.details for c in hard_failures)
            + ". Reconsider the SQL logic (e.g. date/interval direction) and try again."
        )
        return ValidatorOutput(
            status="fail", checks=checks, repairable=True, feedback=feedback, result=result
        )

    return ValidatorOutput(status="pass", checks=checks, repairable=False, result=result)
