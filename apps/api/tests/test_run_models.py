"""Sanity checks on the runs ORM model -- pure metadata introspection, no
database connection needed.
"""

from __future__ import annotations

import app.db.run_models  # noqa: F401  (registers runs.* tables on Base.metadata)
from app.db.base import Base

EXPECTED_TABLES = {"runs.run"}


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables.keys()) >= EXPECTED_TABLES


def test_run_id_is_the_primary_key() -> None:
    run = Base.metadata.tables["runs.run"]

    assert [c.name for c in run.primary_key.columns] == ["id"]


def test_json_columns_exist_for_nested_agent_output() -> None:
    run = Base.metadata.tables["runs.run"]

    for column in ("retrieved_context", "attempts", "insight", "clarification_options"):
        assert column in run.columns
