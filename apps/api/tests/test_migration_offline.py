"""Verifies the Alembic migration generates valid-looking SQL in --sql
(offline) mode -- no live database required, so this runs in CI. It does
not prove the SQL executes correctly against a real Postgres; see
docs/progress.md for the live-database verification still owed locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def test_migration_generates_offline_sql() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head", "--sql"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr

    sql = result.stdout
    for expected in (
        "CREATE SCHEMA IF NOT EXISTS organisation",
        "CREATE SCHEMA IF NOT EXISTS marketplace",
        "CREATE SCHEMA IF NOT EXISTS analytics",
        "CREATE TABLE organisation.department",
        "CREATE TABLE organisation.account",
        "CREATE TABLE marketplace.projects",
        "CREATE TABLE marketplace.task",
        "CREATE OR REPLACE VIEW analytics.v_snapshot",
        "CREATE OR REPLACE VIEW analytics.v_task_lifecycle",
        "CREATE OR REPLACE VIEW analytics.v_project_status",
        "CREATE ROLE bi_readonly",
        "GRANT SELECT ON ALL TABLES IN SCHEMA organisation, marketplace, analytics TO bi_readonly",
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE SCHEMA IF NOT EXISTS catalog",
        "CREATE TABLE catalog.document",
        "CREATE TABLE catalog.chunk",
        "embedding VECTOR(256) NOT NULL",
        "CREATE INDEX ix_chunk_embedding_hnsw ON catalog.chunk USING hnsw",
    ):
        assert expected in sql, f"expected {expected!r} in generated SQL"
