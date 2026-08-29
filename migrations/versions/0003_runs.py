"""runs schema: persisted orchestrator run state

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29

Creates `runs.run` (app.db.run_models.Run): one row per question run,
holding the full RunSnapshot (app.orchestrator.schema) as scalar columns
plus JSONB for the nested agent outputs (retrieved context, NL2SQL/
Validator attempts, Insight). Backs GET /api/v1/runs/{run_id} ("full safe
run state"), GET /api/v1/runs (history) and SSE reconnection-by-run_id.

Application infrastructure, like `catalog.*` -- not warehouse business
data -- so it is not exposed to the read-only bi_readonly role.

Deliberately one wide table rather than docs/06_DATA_MODEL_API_CONTRACTS.md's
fully normalized run/sql_attempt/validation/query_result/insight entities;
see app.db.run_models's module docstring for the rationale.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS runs")

    op.create_table(
        "run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "retrieved_context", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("attempts", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("insight", postgresql.JSONB(), nullable=True),
        sa.Column("insight_error", sa.Text(), nullable=True),
        sa.Column("clarification_question", sa.Text(), nullable=True),
        sa.Column("clarification_options", postgresql.JSONB(), nullable=True),
        sa.Column("clarification_answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="runs",
    )
    op.create_index(
        "ix_run_tenant_created", "run", ["tenant_id", "created_at"], schema="runs"
    )


def downgrade() -> None:
    op.drop_table("run", schema="runs")
    op.execute("DROP SCHEMA IF EXISTS runs")
