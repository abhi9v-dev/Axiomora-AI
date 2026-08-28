from __future__ import annotations

from app.validator.result_checks import (
    check_comparison_period_completeness,
    check_non_negative_columns,
    check_not_empty,
    check_not_truncated,
)
from app.validator.schema import QueryResult


def _result(columns: list[str], rows: list[list[object]], truncated: bool = False) -> QueryResult:
    return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)


def test_not_empty_check_passes_with_rows() -> None:
    result = _result(["x"], [[1], [2]])

    check = check_not_empty(result)

    assert check.status == "pass"
    assert "2" in check.details


def test_not_empty_check_still_passes_on_zero_rows() -> None:
    """An empty result is a valid outcome (docs/08's AT-05), not a
    failure -- Insight generation explains it rather than the Validator
    rejecting it."""
    result = _result(["x"], [])

    check = check_not_empty(result)

    assert check.status == "pass"
    assert "no rows" in check.details.lower()


def test_truncation_check_warns_when_truncated() -> None:
    result = _result(["x"], [[1]], truncated=True)

    check = check_not_truncated(result, row_limit=5000)

    assert check.status == "warning"
    assert "5000" in check.details


def test_truncation_check_passes_when_not_truncated() -> None:
    result = _result(["x"], [[1]], truncated=False)

    check = check_not_truncated(result, row_limit=5000)

    assert check.status == "pass"


def test_non_negative_check_passes_when_no_monitored_columns_present() -> None:
    result = _result(["taskname"], [["x"]])

    check = check_non_negative_columns(result, non_negative_columns={"assignee_hold_hrs"})

    assert check.status == "pass"
    assert "No monitored columns" in check.details


def test_non_negative_check_passes_when_all_values_non_negative() -> None:
    result = _result(["assignee_hold_hrs"], [[0.0], [12.5], [100.0]])

    check = check_non_negative_columns(result, non_negative_columns={"assignee_hold_hrs"})

    assert check.status == "pass"


def test_non_negative_check_fails_on_a_negative_value() -> None:
    result = _result(["department", "assignee_hold_hrs"], [["Buyer", -3.5], ["Finance", 10.0]])

    check = check_non_negative_columns(result, non_negative_columns={"assignee_hold_hrs"})

    assert check.status == "fail"
    assert "assignee_hold_hrs" in check.details


def test_non_negative_check_handles_decimal_values() -> None:
    from decimal import Decimal

    result = _result(["assignee_hold_hrs"], [[Decimal("-1.0")]])

    check = check_non_negative_columns(result, non_negative_columns={"assignee_hold_hrs"})

    assert check.status == "fail"


def test_non_negative_check_ignores_null_values() -> None:
    result = _result(["assignee_hold_hrs"], [[None], [5.0]])

    check = check_non_negative_columns(result, non_negative_columns={"assignee_hold_hrs"})

    assert check.status == "pass"


def test_comparison_period_check_returns_none_when_no_period_column() -> None:
    result = _result(["department_name"], [["Buyer"]])

    check = check_comparison_period_completeness(result)

    assert check is None


def test_comparison_period_check_warns_on_a_single_period() -> None:
    result = _result(["quarter", "median_hold_hrs"], [["2026-Q2", 23.1]])

    check = check_comparison_period_completeness(result)

    assert check is not None
    assert check.status == "warning"


def test_comparison_period_check_passes_with_multiple_periods() -> None:
    result = _result(
        ["quarter", "median_hold_hrs"],
        [["2026-Q1", 13.8], ["2026-Q2", 23.1], ["2026-Q3", 19.7]],
    )

    check = check_comparison_period_completeness(result)

    assert check is not None
    assert check.status == "pass"
