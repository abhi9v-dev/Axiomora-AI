"""SQLAlchemy ORM model for a recorded action
(docs/06_DATA_MODEL_API_CONTRACTS.md's `action` entity), application
infrastructure like `runs.run` and `catalog.*` -- not warehouse business
data.

The unique constraint on (run_id, idempotency_key) is what actually
enforces idempotency (docs/07_SECURITY_GOVERNANCE.md: "action requests use
idempotency keys") at the database level, not just in application code --
app.action.store relies on catching its violation to detect a duplicate
request race rather than a plain existence check racing a concurrent
insert.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_TZ = DateTime(timezone=True)


class Action(Base):
    __tablename__ = "action"
    __table_args__ = (
        UniqueConstraint("run_id", "idempotency_key", name="uq_action_run_idempotency_key"),
        {"schema": "runs"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.run.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(_TZ)
