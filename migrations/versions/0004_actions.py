"""runs.action: recorded action requests (export, and later Power BI)

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-30

Creates `runs.action` (app.db.action_models.Action): one row per action
request against a run, whether approved-and-completed or policy-rejected
(docs/07_SECURITY_GOVERNANCE.md: "audit events... action approvals and
outcomes" -- rejection is an outcome too). The unique constraint on
(run_id, idempotency_key) is what actually enforces
docs/06_DATA_MODEL_API_CONTRACTS.md's idempotency-key requirement at the
database level.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("runs.run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "idempotency_key", name="uq_action_run_idempotency_key"),
        schema="runs",
    )
    op.create_index("ix_action_run_id", "action", ["run_id"], schema="runs")


def downgrade() -> None:
    op.drop_table("action", schema="runs")
