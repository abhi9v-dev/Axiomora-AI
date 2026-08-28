"""Result-shape and domain validation (FR-007).

Runs only after a query has executed successfully. Each function produces
one ValidationCheck (or None if not applicable); the overall pass/fail/
repairable verdict is decided by app.validator.agent, not here -- this
module only observes and reports what the data looks like.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from decimal import Decimal

from app.validator.schema import QueryResult, ValidationCheck

_NUMERIC_TYPES = (int, float, Decimal)

DEFAULT_PERIOD_COLUMN_NAMES = frozenset({"quarter", "period", "month"})


def check_not_empty(result: QueryResult) -> ValidationCheck:
    # An empty result is a valid outcome, not a failure -- Insight
    # generation (Phase 5) explains "no data found" rather than inventing
    # one (docs/08's AT-05).
    details = (
        "Query returned no rows."
        if result.row_count == 0
        else f"{result.row_count} row(s) returned."
    )
    return ValidationCheck(name="result_not_empty", status="pass", details=details)


def check_not_truncated(result: QueryResult, *, row_limit: int) -> ValidationCheck:
    if result.truncated:
        return ValidationCheck(
            name="result_row_limit",
            status="warning",
            details=f"Result was truncated at the {row_limit}-row limit; more rows may exist.",
        )
    return ValidationCheck(
        name="result_row_limit", status="pass", details=f"Within the {row_limit}-row limit."
    )


def check_non_negative_columns(
    result: QueryResult, *, non_negative_columns: AbstractSet[str]
) -> ValidationCheck:
    """data/glossary/validation_rules.yaml's hold_hours_non_negative and
    similar rules: duration/count measures must never be negative. A
    negative value indicates a genuine bug (e.g. reversed date
    arithmetic), so unlike the other result checks, this one is a hard
    failure worth a repair attempt."""
    present = sorted(c for c in non_negative_columns if c in result.columns)
    if not present:
        return ValidationCheck(
            name="non_negative_columns", status="pass", details="No monitored columns present."
        )

    indices = {c: result.columns.index(c) for c in present}
    offending: set[str] = set()
    for row in result.rows:
        for column, index in indices.items():
            value = row[index]
            if isinstance(value, _NUMERIC_TYPES) and value < 0:
                offending.add(column)

    if offending:
        return ValidationCheck(
            name="non_negative_columns",
            status="fail",
            details=f"Column(s) {', '.join(sorted(offending))} contained a negative value.",
        )
    return ValidationCheck(
        name="non_negative_columns", status="pass", details=f"{', '.join(present)} are all >= 0."
    )


def check_comparison_period_completeness(
    result: QueryResult, *, period_column_names: frozenset[str] = DEFAULT_PERIOD_COLUMN_NAMES
) -> ValidationCheck | None:
    """Best-effort heuristic: if the result is grouped by something that
    looks like a time period and only one period is present, flag it --
    the question may have intended a comparison across periods that the
    query only partially answered. Not a hard failure: a genuinely
    single-period question is entirely legitimate too. Returns None when
    no period-like column is present (not applicable to this query)."""
    period_col = next((c for c in result.columns if c.lower() in period_column_names), None)
    if period_col is None:
        return None

    index = result.columns.index(period_col)
    distinct_periods = {row[index] for row in result.rows}
    if len(distinct_periods) <= 1:
        return ValidationCheck(
            name="comparison_period_completeness",
            status="warning",
            details=(
                f"Only {len(distinct_periods)} distinct value(s) of '{period_col}' were "
                "returned; if the question asked for a comparison, confirm this is expected."
            ),
        )
    return ValidationCheck(
        name="comparison_period_completeness",
        status="pass",
        details=f"{len(distinct_periods)} distinct value(s) of '{period_col}' returned.",
    )
