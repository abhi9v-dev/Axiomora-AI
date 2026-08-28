from __future__ import annotations

from app.validator.allowlist import ALLOWED_ANONYMOUS_FUNCTIONS, ALLOWED_OBJECTS


def test_allowlist_has_exactly_the_seven_warehouse_tables_and_three_views() -> None:
    assert len(ALLOWED_OBJECTS) == 10


def test_allowlist_includes_the_known_warehouse_tables() -> None:
    for expected in (
        ("marketplace", "task"),
        ("marketplace", "projects"),
        ("marketplace", "projectstage"),
        ("marketplace", "projectstatus"),
        ("marketplace", "project_sub_status"),
        ("organisation", "department"),
        ("organisation", "account"),
    ):
        assert expected in ALLOWED_OBJECTS


def test_allowlist_includes_the_three_analytics_views() -> None:
    for expected in (
        ("analytics", "v_snapshot"),
        ("analytics", "v_task_lifecycle"),
        ("analytics", "v_project_status"),
    ):
        assert expected in ALLOWED_OBJECTS


def test_allowlist_never_includes_the_catalog_schema() -> None:
    """catalog.* is embedding/application infrastructure, never queryable
    by generated warehouse SQL (docs/03_ARCHITECTURE.md's data-store
    split)."""
    assert not any(schema == "catalog" for schema, _table in ALLOWED_OBJECTS)


def test_anonymous_function_allowlist_is_small_and_explicit() -> None:
    """A large allowlist here would defeat the point -- every dangerous
    Postgres function (pg_read_file, dblink, pg_sleep, ...) parses as
    exp.Anonymous, so this list must stay short and deliberately curated."""
    assert frozenset({"age"}) == ALLOWED_ANONYMOUS_FUNCTIONS
