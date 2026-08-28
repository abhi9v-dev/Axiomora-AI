"""Sanity checks on the warehouse ORM models -- pure metadata introspection,
no database connection needed. Guards against silently drifting away from
the real schema this project's tables are modeled on (see docs/adr/0003).
"""

from __future__ import annotations

from sqlalchemy import DateTime

from app.db.models import Base

EXPECTED_TABLES = {
    "organisation.department",
    "organisation.account",
    "marketplace.projectstage",
    "marketplace.projectstatus",
    "marketplace.project_sub_status",
    "marketplace.projects",
    "marketplace.task",
}


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_lookup_table_primary_keys_match_source_schema() -> None:
    """The source schema uses bespoke PK names on two lookup tables (not
    `id`) -- preserve that exactly rather than "cleaning it up"."""
    projectstage = Base.metadata.tables["marketplace.projectstage"]
    projectstatus = Base.metadata.tables["marketplace.projectstatus"]
    project_sub_status = Base.metadata.tables["marketplace.project_sub_status"]

    assert [c.name for c in projectstage.primary_key.columns] == ["projectstage"]
    assert [c.name for c in projectstatus.primary_key.columns] == ["project_status"]
    assert [c.name for c in project_sub_status.primary_key.columns] == ["id"]


def test_task_foreign_keys_target_expected_tables() -> None:
    task = Base.metadata.tables["marketplace.task"]
    fk_targets = {fk.target_fullname for fk in task.foreign_keys}

    assert "marketplace.projects.projectid" in fk_targets
    assert "organisation.department.departmentid" in fk_targets
    assert "organisation.account.accountid" in fk_targets


def test_projects_foreign_keys_target_lookup_tables() -> None:
    projects = Base.metadata.tables["marketplace.projects"]
    fk_targets = {fk.target_fullname for fk in projects.foreign_keys}

    assert "marketplace.projectstage.projectstage" in fk_targets
    assert "marketplace.projectstatus.project_status" in fk_targets
    assert "marketplace.project_sub_status.id" in fk_targets


def test_timestamp_columns_are_timezone_aware() -> None:
    task = Base.metadata.tables["marketplace.task"]
    for column_name in ("createddatetime", "claimedon", "startedon", "completedon"):
        column_type = task.columns[column_name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True, column_name
