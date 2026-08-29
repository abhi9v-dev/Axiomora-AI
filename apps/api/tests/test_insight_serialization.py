from __future__ import annotations

import pytest

from app.insight.serialization import CellReferenceError, cell_id, resolve_cell, serialize_result
from app.validator.schema import QueryResult

_RESULT = QueryResult(
    columns=["department_name", "quarter", "median_hold_hrs"],
    rows=[
        ["Buyer", "Q1", 9.5],
        ["Buyer", "Q2", 27.4],
    ],
    row_count=2,
    truncated=False,
)


def test_cell_id_is_one_indexed() -> None:
    assert cell_id(1, 1) == "result:r1:c1"
    assert cell_id(2, 3) == "result:r2:c3"


def test_resolve_cell_returns_the_named_value() -> None:
    assert resolve_cell(_RESULT, "result:r1:c3") == 9.5
    assert resolve_cell(_RESULT, "result:r2:c3") == 27.4
    assert resolve_cell(_RESULT, "result:r2:c1") == "Buyer"


def test_resolve_cell_rejects_malformed_reference() -> None:
    with pytest.raises(CellReferenceError):
        resolve_cell(_RESULT, "not-a-cell-ref")


@pytest.mark.parametrize("ref", ["result:r0:c1", "result:r3:c1", "result:r1:c0", "result:r1:c4"])
def test_resolve_cell_rejects_out_of_range_reference(ref: str) -> None:
    with pytest.raises(CellReferenceError):
        resolve_cell(_RESULT, ref)


def test_serialize_result_includes_every_cell_id_and_value() -> None:
    text = serialize_result(_RESULT)

    assert "c1=department_name" in text
    assert "c3=median_hold_hrs" in text
    assert "r1:" in text and "r2:" in text
    assert "9.5" in text
    assert "27.4" in text
    assert "'Buyer'" in text


def test_serialize_empty_result_is_explicitly_labeled() -> None:
    empty = QueryResult(columns=["a"], rows=[], row_count=0, truncated=False)

    assert serialize_result(empty) == "(no rows)"
