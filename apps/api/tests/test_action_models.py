"""Sanity checks on the action ORM model -- pure metadata introspection, no
database connection needed.
"""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

import app.db.action_models  # noqa: F401  (registers runs.action on Base.metadata)
from app.db.base import Base

EXPECTED_TABLES = {"runs.action"}


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables.keys()) >= EXPECTED_TABLES


def test_run_id_references_the_run_table() -> None:
    action = Base.metadata.tables["runs.action"]
    fk_targets = {fk.target_fullname for fk in action.foreign_keys}

    assert "runs.run.id" in fk_targets


def test_run_id_and_idempotency_key_are_unique_together() -> None:
    action = Base.metadata.tables["runs.action"]
    unique_column_sets = [
        {c.name for c in constraint.columns}
        for constraint in action.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert {"run_id", "idempotency_key"} in unique_column_sets
