"""MockPowerBIAdapter -- pure Python, no network, deterministic record of
every call it receives. Mirrors the style of test_llm_fake.py for
FakeLLMProvider."""

from __future__ import annotations

from app.action.power_bi.mock import MockPowerBIAdapter


async def test_push_rows_records_the_call_and_reports_the_row_count() -> None:
    adapter = MockPowerBIAdapter()
    rows: list[dict[str, object]] = [{"a": 1}, {"a": 2}]

    result = await adapter.push_rows(dataset_id="ds-1", table_name="Table1", rows=rows)

    assert result.dataset_id == "ds-1"
    assert result.table_name == "Table1"
    assert result.rows_pushed == 2
    assert adapter.pushed_calls == [("ds-1", "Table1", rows)]


async def test_push_rows_with_no_rows_reports_zero() -> None:
    adapter = MockPowerBIAdapter()

    result = await adapter.push_rows(dataset_id="ds-1", table_name="Table1", rows=[])

    assert result.rows_pushed == 0


async def test_refresh_dataset_records_the_call_and_returns_a_unique_request_id() -> None:
    adapter = MockPowerBIAdapter()

    first = await adapter.refresh_dataset(dataset_id="ds-1")
    second = await adapter.refresh_dataset(dataset_id="ds-1")

    assert adapter.refresh_calls == ["ds-1", "ds-1"]
    assert first.dataset_id == "ds-1"
    assert first.refresh_request_id != second.refresh_request_id


async def test_calls_to_different_methods_are_tracked_independently() -> None:
    adapter = MockPowerBIAdapter()

    await adapter.push_rows(dataset_id="ds-1", table_name="Table1", rows=[{"a": 1}])
    await adapter.refresh_dataset(dataset_id="ds-2")

    assert len(adapter.pushed_calls) == 1
    assert len(adapter.refresh_calls) == 1
