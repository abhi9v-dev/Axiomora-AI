"""Deterministic synthetic seed data for the marketplace-operations warehouse.

Every row is fabricated (see docs/adr/0003-marketplace-operations-demo-domain.md)
except `organisation.department`, which is loaded verbatim from the real
(confirmed-synthetic) data/seed/organisation_department.csv fixture. Every
other table is generated from a fixed random seed, so re-running the
generator -- `python -m app.db.seed` -- always produces byte-identical rows
and can be run repeatedly against the same database.

The generator deliberately encodes one discoverable business result, used
as ground truth in later phases: in Q2 2026, the Buyer department's median
task hold time (claim to completion) spikes, driven by "Compliance Review"
tasks (a subtype of "Supplier Onboarding") taking far longer than usual to
be claimed and completed. See the ANOMALY_* constants below.
"""

from __future__ import annotations

import asyncio
import csv
import datetime as dt
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.db.models import (
    Account,
    Department,
    Project,
    ProjectStage,
    ProjectStatus,
    ProjectSubStatus,
    Task,
)

SeedRow = dict[str, Any]

# datetime.timezone.utc rather than zoneinfo.ZoneInfo("UTC") -- the latter
# needs the IANA tzdata database, which isn't guaranteed present on Windows
# without the separate `tzdata` package. UTC-only arithmetic doesn't need it.
UTC = dt.UTC
SEED = 20260828  # fixed so the generator is byte-for-byte reproducible

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DEPARTMENT_CSV = REPO_ROOT / "data" / "seed" / "organisation_department.csv"

# --- deliberate seed anomaly: the Phase 1 "known business result" ---
ANOMALY_DEPARTMENT = "Buyer"
ANOMALY_TASKTYPE = "Supplier Onboarding"
ANOMALY_SUBTYPE = "Compliance Review"
ANOMALY_QUARTER_START = dt.datetime(2026, 4, 1, tzinfo=UTC)
ANOMALY_QUARTER_END = dt.datetime(2026, 7, 1, tzinfo=UTC)  # exclusive
ANOMALY_HOLD_HOURS_RANGE = (48.0, 96.0)
ANOMALY_AFFECTED_FRACTION = 0.8  # leave ~20% at baseline so the pattern isn't suspiciously clean
BASELINE_HOLD_HOURS_RANGE = (2.0, 30.0)

HORIZON_START = dt.datetime(2025, 10, 1, tzinfo=UTC)
HORIZON_END = dt.datetime(2026, 8, 20, tzinfo=UTC)  # latest allowed createddatetime
ABSOLUTE_CEILING = dt.datetime(2026, 8, 28, tzinfo=UTC)  # "now" -- no timestamp may exceed this

PROJECT_COUNT = 150
FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
    "Riley",
    "Jamie",
    "Avery",
    "Quinn",
    "Drew",
    "Sam",
    "Charlie",
    "Robin",
    "Skyler",
    "Reese",
    "Emerson",
    "Rowan",
    "Finley",
    "Hayden",
    "Peyton",
    "Dana",
    "Kendall",
    "Blair",
    "Sage",
]
LAST_NAMES = [
    "Bennett",
    "Ramirez",
    "Chen",
    "Okafor",
    "Nakamura",
    "Singh",
    "Larsen",
    "Fitzgerald",
    "Kowalski",
    "Mensah",
    "Petrov",
    "Alvarez",
    "Hughes",
    "Novak",
    "Silva",
    "Andersson",
    "Haddad",
    "Okonkwo",
    "Dubois",
    "Ferreira",
]
ACCOUNT_COUNT = 40

PROJECT_STAGES = [
    (1, "Intake"),
    (2, "Sourcing"),
    (3, "Delivery"),
    (4, "Closeout"),
]
PROJECT_STATUSES = [
    (1, "Draft"),
    (2, "Active"),
    (3, "On Hold"),
    (4, "Completed"),
    (5, "Archived"),
]
PROJECT_SUB_STATUSES = [
    (1, "Pending Approval"),
    (2, "In Review"),
    (3, "Blocked"),
    (4, "Ready to Close"),
]
PROJECT_CATEGORIES = [
    "Procurement",
    "Onboarding",
    "Sourcing",
    "Delivery",
    "Customer Success",
]


@dataclass(frozen=True)
class TaskCatalogEntry:
    subtypes: list[str]
    departments: list[tuple[str, int]]


# tasktype -> subtypes and the departments that handle it (with selection weights)
TASK_CATALOG: dict[str, TaskCatalogEntry] = {
    "Supplier Onboarding": TaskCatalogEntry(
        subtypes=["Compliance Review", "Bank Details Verification", "Contract Signature"],
        departments=[("Buyer", 7), ("Procurement Assurance", 3)],
    ),
    "Sourcing Request": TaskCatalogEntry(
        subtypes=["RFQ Preparation", "Quote Comparison"],
        departments=[("Procurement Business Partner", 5), ("Procurement Specialist Team", 5)],
    ),
    "Delivery Confirmation": TaskCatalogEntry(
        subtypes=["Goods Receipt", "Invoice Match"],
        departments=[("Delivery Team", 6), ("Finance", 4)],
    ),
    "Customer Escalation": TaskCatalogEntry(
        subtypes=["Initial Triage", "Resolution"],
        departments=[("Customer Experience", 6), ("Sales and Account Manager", 4)],
    ),
    "Internal Review": TaskCatalogEntry(
        subtypes=["Data Quality Check", "Policy Update"],
        departments=[("Bloom", 3), ("Procurement Assurance", 3), ("Finance", 2)],
    ),
}
TASKTYPE_WEIGHTS = [
    ("Supplier Onboarding", 4),
    ("Sourcing Request", 3),
    ("Delivery Confirmation", 2),
    ("Customer Escalation", 2),
    ("Internal Review", 1),
]


@dataclass
class SeedData:
    departments: list[SeedRow] = field(default_factory=list)
    accounts: list[SeedRow] = field(default_factory=list)
    project_stages: list[SeedRow] = field(default_factory=list)
    project_statuses: list[SeedRow] = field(default_factory=list)
    project_sub_statuses: list[SeedRow] = field(default_factory=list)
    projects: list[SeedRow] = field(default_factory=list)
    tasks: list[SeedRow] = field(default_factory=list)


def _weighted_choice(rng: random.Random, options: list[tuple[str, int]]) -> str:
    names = [name for name, _weight in options]
    weights = [weight for _name, weight in options]
    return rng.choices(names, weights=weights, k=1)[0]


def load_departments(csv_path: Path = DEFAULT_DEPARTMENT_CSV) -> list[SeedRow]:
    """Load the real (confirmed-synthetic) department fixture verbatim."""
    rows: list[SeedRow] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            rows.append(
                {
                    "departmentid": int(raw["departmentid"]),
                    "departmentname": raw["departmentname"],
                    "description": raw["description"] or None,
                    "createdby": raw["createdby"] or None,
                    "creationdate": dt.datetime.fromisoformat(raw["creationdate"]),
                    "lastmodifiedby": raw["lastmodifiedby"] or None,
                    "lastmodifieddate": (
                        dt.datetime.fromisoformat(raw["lastmodifieddate"])
                        if raw["lastmodifieddate"]
                        else None
                    ),
                }
            )
    return rows


def _generate_accounts(rng: random.Random) -> list[SeedRow]:
    pairs = {(first, last) for first in FIRST_NAMES for last in LAST_NAMES}
    chosen = rng.sample(sorted(pairs), k=ACCOUNT_COUNT)
    return [
        {"accountid": i, "forename": forename, "surname": surname}
        for i, (forename, surname) in enumerate(chosen, start=1)
    ]


def _random_datetime(rng: random.Random, start: dt.datetime, end: dt.datetime) -> dt.datetime:
    span = (end - start).total_seconds()
    offset = rng.uniform(0, max(span, 0.0))
    return start + dt.timedelta(seconds=offset)


def _generate_projects(rng: random.Random) -> list[SeedRow]:
    projects = []
    for i in range(1, PROJECT_COUNT + 1):
        creationdate = _random_datetime(rng, HORIZON_START, HORIZON_END)
        age_days = (HORIZON_END - creationdate).days
        # Older projects are more likely to have reached a terminal status.
        if age_days > 240:
            status = _weighted_choice(rng, [("Completed", 6), ("Archived", 3), ("On Hold", 1)])
        elif age_days > 90:
            status = _weighted_choice(
                rng, [("Active", 4), ("Completed", 3), ("On Hold", 2), ("Archived", 1)]
            )
        else:
            status = _weighted_choice(rng, [("Draft", 2), ("Active", 6), ("On Hold", 2)])
        status_id = next(sid for sid, name in PROJECT_STATUSES if name == status)

        stage = rng.choice(PROJECT_STAGES)[0]
        sub_status = rng.choice(PROJECT_SUB_STATUSES + [None, None])  # frequently unset
        category = rng.choice(PROJECT_CATEGORIES)
        submitted = None
        if rng.random() > 0.15:
            max_offset_hrs = min(72.0, (ABSOLUTE_CEILING - creationdate).total_seconds() / 3600.0)
            if max_offset_hrs >= 1.0:
                submitted = creationdate + dt.timedelta(hours=rng.uniform(1, max_offset_hrs))

        projects.append(
            {
                "projectid": i,
                "projectname": f"{category} Initiative #{i:04d}",
                "stage": stage,
                "status": status_id,
                "project_sub_status_id": sub_status[0] if sub_status else None,
                "projectcategory": category,
                "creationdate": creationdate,
                "submittedat": submitted,
            }
        )
    return projects


def _quarter_label(moment: dt.datetime) -> str:
    return f"{moment.year}-Q{(moment.month - 1) // 3 + 1}"


def _is_anomaly_slice(department: str, tasktype: str, subtype: str, created: dt.datetime) -> bool:
    return (
        department == ANOMALY_DEPARTMENT
        and tasktype == ANOMALY_TASKTYPE
        and subtype == ANOMALY_SUBTYPE
        and ANOMALY_QUARTER_START <= created < ANOMALY_QUARTER_END
    )


def _generate_tasks(
    rng: random.Random, projects: list[SeedRow], accounts: list[SeedRow], departments: list[SeedRow]
) -> list[SeedRow]:
    dept_id_by_name = {d["departmentname"]: d["departmentid"] for d in departments}
    account_ids = [a["accountid"] for a in accounts]

    tasks: list[SeedRow] = []
    taskid = 1
    for project in projects:
        n_tasks = rng.randint(3, 10)
        window_end = min(project["creationdate"] + dt.timedelta(days=60), HORIZON_END)
        for _ in range(n_tasks):
            tasktype = _weighted_choice(rng, TASKTYPE_WEIGHTS)
            catalog_entry = TASK_CATALOG[tasktype]
            subtype = rng.choice(catalog_entry.subtypes)
            department = _weighted_choice(rng, catalog_entry.departments)
            departmentid = dept_id_by_name[department]

            earliest_end = project["creationdate"] + dt.timedelta(hours=1)
            created = _random_datetime(rng, project["creationdate"], max(window_end, earliest_end))

            assignee_id = rng.choice(account_ids) if rng.random() > 0.05 else None
            claimed = started = completed = None
            taskstatus = "Open"

            if assignee_id is not None:
                claim_wait_hrs = rng.uniform(0.5, 48.0)
                candidate_claimed = created + dt.timedelta(hours=claim_wait_hrs)

                # Never invent a timestamp after "now": if claiming this task
                # would land in the future, it simply hasn't been claimed
                # yet. This keeps created <= claimed <= started <= completed
                # by construction, with no backward clamp that could break
                # that ordering.
                if candidate_claimed <= ABSOLUTE_CEILING:
                    claimed = candidate_claimed
                    taskstatus = "Claimed"

                    is_anomaly = _is_anomaly_slice(department, tasktype, subtype, created)
                    will_complete = rng.random() > 0.10  # ~10% stay in progress regardless

                    if will_complete:
                        if is_anomaly and rng.random() < ANOMALY_AFFECTED_FRACTION:
                            hold_hrs = rng.uniform(*ANOMALY_HOLD_HOURS_RANGE)
                        else:
                            hold_hrs = rng.uniform(*BASELINE_HOLD_HOURS_RANGE)
                        candidate_completed = claimed + dt.timedelta(hours=hold_hrs)

                        if candidate_completed <= ABSOLUTE_CEILING:
                            completed = candidate_completed
                            taskstatus = "Completed"
                            # ~52% of completions omit startedon, matching
                            # the real system's documented coverage gap.
                            if rng.random() > 0.52:
                                start_delay_hrs = rng.uniform(0.0, max(hold_hrs / 4, 0.5))
                                started = min(
                                    claimed + dt.timedelta(hours=start_delay_hrs), completed
                                )
                        # else: still claimed, hasn't had time to complete yet.
                    else:
                        if rng.random() > 0.5:
                            candidate_started = claimed + dt.timedelta(hours=rng.uniform(0.5, 12.0))
                            if candidate_started <= ABSOLUTE_CEILING:
                                started = candidate_started
                        taskstatus = "In Progress" if started else "Claimed"
                # else: still unclaimed -- created but claiming would be in the future.

            tasks.append(
                {
                    "taskid": taskid,
                    "taskname": f"{subtype} ({tasktype})",
                    "tasktype": tasktype,
                    "tasksubtype": subtype,
                    "taskstatus": taskstatus,
                    "projectid": project["projectid"],
                    "departmentid": departmentid,
                    "assigneeaccountid": assignee_id,
                    "completedbyaccountid": assignee_id if completed is not None else None,
                    "createddatetime": created,
                    "claimedon": claimed,
                    "startedon": started,
                    "completedon": completed,
                }
            )
            taskid += 1
    return tasks


def generate_seed_data(
    department_csv_path: Path = DEFAULT_DEPARTMENT_CSV, seed: int = SEED
) -> SeedData:
    """Pure, deterministic generator -- no I/O beyond reading the department CSV."""
    rng = random.Random(seed)
    departments = load_departments(department_csv_path)
    accounts = _generate_accounts(rng)
    projects = _generate_projects(rng)
    tasks = _generate_tasks(rng, projects, accounts, departments)

    return SeedData(
        departments=departments,
        accounts=accounts,
        project_stages=[{"projectstage": pid, "name": name} for pid, name in PROJECT_STAGES],
        project_statuses=[{"project_status": pid, "name": name} for pid, name in PROJECT_STATUSES],
        project_sub_statuses=[{"id": pid, "name": name} for pid, name in PROJECT_SUB_STATUSES],
        projects=projects,
        tasks=tasks,
    )


_TRUNCATE_SQL = text(
    "TRUNCATE TABLE marketplace.task, marketplace.projects, "
    "marketplace.project_sub_status, marketplace.projectstatus, "
    "marketplace.projectstage, organisation.account, organisation.department "
    "RESTART IDENTITY CASCADE"
)


async def seed_database(
    engine: AsyncEngine, department_csv_path: Path = DEFAULT_DEPARTMENT_CSV, seed: int = SEED
) -> SeedData:
    """Repeatable seed: truncates the warehouse tables, then reinserts deterministic rows."""
    data = generate_seed_data(department_csv_path, seed)
    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE_SQL)
        await conn.execute(insert(Department), data.departments)
        await conn.execute(insert(Account), data.accounts)
        await conn.execute(insert(ProjectStage), data.project_stages)
        await conn.execute(insert(ProjectStatus), data.project_statuses)
        await conn.execute(insert(ProjectSubStatus), data.project_sub_statuses)
        await conn.execute(insert(Project), data.projects)
        await conn.execute(insert(Task), data.tasks)
    return data


async def _main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        data = await seed_database(engine)
        print(
            f"Seeded {len(data.departments)} departments, {len(data.accounts)} accounts, "
            f"{len(data.project_stages)} project stages, {len(data.project_statuses)} "
            f"project statuses, {len(data.project_sub_statuses)} project sub-statuses, "
            f"{len(data.projects)} projects, {len(data.tasks)} tasks."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
