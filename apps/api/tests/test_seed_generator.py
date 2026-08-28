"""Tests for the deterministic marketplace-operations seed generator.

These run against the generator's in-memory output only -- no database is
needed -- so they can assert the Phase 1 "known business result" (see
docs/adr/0003-marketplace-operations-demo-domain.md) is really encoded in
the data, independent of whether a warehouse is available to load it into.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from statistics import median
from typing import Any

from app.db.seed import (
    ACCOUNT_COUNT,
    ANOMALY_DEPARTMENT,
    ANOMALY_SUBTYPE,
    ANOMALY_TASKTYPE,
    DEFAULT_DEPARTMENT_CSV,
    PROJECT_COUNT,
    SeedData,
    _quarter_label,
    generate_seed_data,
    load_departments,
)


def test_generator_is_deterministic() -> None:
    first = generate_seed_data()
    second = generate_seed_data()

    assert first == second


def test_generator_row_counts() -> None:
    data = generate_seed_data()

    assert len(data.departments) == 10
    assert len(data.accounts) == ACCOUNT_COUNT
    assert len(data.project_stages) == 4
    assert len(data.project_statuses) == 5
    assert len(data.project_sub_statuses) == 4
    assert len(data.projects) == PROJECT_COUNT
    # 3-10 tasks per project.
    assert PROJECT_COUNT * 3 <= len(data.tasks) <= PROJECT_COUNT * 10


def test_departments_load_from_real_csv_fixture() -> None:
    departments = load_departments(DEFAULT_DEPARTMENT_CSV)

    names_by_id = {d["departmentid"]: d["departmentname"] for d in departments}
    assert names_by_id[5] == "Buyer"
    assert names_by_id[9] == "Bloom"
    assert len(departments) == 10


def test_task_timestamps_are_never_out_of_order() -> None:
    """Mirrors the source system's 'ANOMALY_ORDER' quality flag: our synthetic
    tasks must never trigger it (created <= claimed <= started <= completed)."""
    data = generate_seed_data()

    for task in data.tasks:
        created = task["createddatetime"]
        claimed = task["claimedon"]
        started = task["startedon"]
        completed = task["completedon"]

        if claimed is not None:
            assert claimed >= created, task
        if started is not None and claimed is not None:
            assert started >= claimed, task
        if completed is not None and started is not None:
            assert completed >= started, task
        if completed is not None and claimed is not None and started is None:
            assert completed >= claimed, task
        if completed is not None:
            assert completed >= created, task


def test_project_and_task_ids_are_dense_and_unique() -> None:
    data = generate_seed_data()

    project_ids = [p["projectid"] for p in data.projects]
    task_ids = [t["taskid"] for t in data.tasks]

    assert project_ids == list(range(1, len(project_ids) + 1))
    assert task_ids == list(range(1, len(task_ids) + 1))
    assert {t["projectid"] for t in data.tasks} <= set(project_ids)


def _hold_hours(task: dict[str, Any]) -> float | None:
    if task["claimedon"] is not None and task["completedon"] is not None:
        return float((task["completedon"] - task["claimedon"]).total_seconds() / 3600.0)
    return None


def _median_hold_hours_by_quarter(
    data: SeedData, *, department: str, tasktype: str | None = None, subtype: str | None = None
) -> dict[str, float]:
    dept_name_by_id = {d["departmentid"]: d["departmentname"] for d in data.departments}
    buckets: dict[str, list[float]] = defaultdict(list)

    for task in data.tasks:
        if dept_name_by_id.get(task["departmentid"]) != department:
            continue
        if tasktype is not None and task["tasktype"] != tasktype:
            continue
        if subtype is not None and task["tasksubtype"] != subtype:
            continue
        hold = _hold_hours(task)
        if hold is None:
            continue
        buckets[_quarter_label(task["createddatetime"])].append(hold)

    return {quarter: median(values) for quarter, values in buckets.items() if values}


def test_q2_buyer_compliance_review_hold_time_spike_is_the_known_business_result() -> None:
    """The Phase 1 seed anomaly, verified directly from generated data:
    Buyer-department median task hold time spikes in Q2 2026, and within
    Buyer's Q2 tasks, Supplier Onboarding / Compliance Review is the driver.
    """
    data = generate_seed_data()

    subtype_by_quarter = _median_hold_hours_by_quarter(
        data, department=ANOMALY_DEPARTMENT, tasktype=ANOMALY_TASKTYPE, subtype=ANOMALY_SUBTYPE
    )
    department_by_quarter = _median_hold_hours_by_quarter(data, department=ANOMALY_DEPARTMENT)

    baseline_quarters = ["2025-Q4", "2026-Q1", "2026-Q3"]
    for q in [*baseline_quarters, "2026-Q2"]:
        assert q in subtype_by_quarter, f"missing quarter {q} in anomaly-slice data"
        assert q in department_by_quarter, f"missing quarter {q} in department data"

    baseline_subtype_median = median(subtype_by_quarter[q] for q in baseline_quarters)
    baseline_department_median = median(department_by_quarter[q] for q in baseline_quarters)

    # The subtype most directly carrying the anomaly should roughly triple.
    assert subtype_by_quarter["2026-Q2"] > 2 * baseline_subtype_median

    # The department-wide median (mixing affected and unaffected task types)
    # should rise too, just less dramatically -- it's a real, findable driver
    # relationship, not the entire department being affected uniformly.
    assert department_by_quarter["2026-Q2"] > 1.2 * baseline_department_median

    # Baseline quarters should stay within a similar band of each other
    # (i.e. the spike is specific to Q2, not a general upward drift).
    for q in baseline_quarters:
        assert subtype_by_quarter[q] < 1.5 * baseline_subtype_median


def test_anomaly_window_is_calendar_q2_2026() -> None:
    from app.db.seed import ANOMALY_QUARTER_END, ANOMALY_QUARTER_START

    assert dt.datetime(2026, 4, 1, tzinfo=dt.UTC) == ANOMALY_QUARTER_START
    assert dt.datetime(2026, 7, 1, tzinfo=dt.UTC) == ANOMALY_QUARTER_END
