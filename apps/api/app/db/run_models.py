"""SQLAlchemy ORM model for a persisted run (docs/06_DATA_MODEL_API_CONTRACTS.md's
`run` entity, application infrastructure like `catalog.*` -- not warehouse
business data).

Deliberately one wide table rather than docs/06's fully normalized
`run`/`sql_attempt`/`validation`/`query_result`/`insight` entities: nothing
in this project yet needs to query attempts, checks or results across runs
relationally (e.g. "every validation failure last week"), and a run is
always read and written as one coherent snapshot (GET /runs/{id}, the
Ask/Evidence UI, the orchestrator's own state persistence). JSONB columns
hold the nested agent outputs; app.orchestrator.schema.RunSnapshot is the
one place their shape is defined and validated. If cross-run analytical
queries become a real requirement later, splitting into normalized tables
is a additive migration, not a rewrite.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_TZ = DateTime(timezone=True)


class Run(Base):
    __tablename__ = "run"
    __table_args__ = {"schema": "runs"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)

    # Nested agent outputs, validated against app.orchestrator.schema.RunSnapshot
    # on the way in and out -- never read or written as loose dicts elsewhere.
    retrieved_context: Mapped[list[object]] = mapped_column(JSONB, default=list)
    attempts: Mapped[list[object]] = mapped_column(JSONB, default=list)
    insight: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    insight_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    clarification_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    clarification_options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    clarification_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(_TZ)
    updated_at: Mapped[dt.datetime] = mapped_column(_TZ)
    completed_at: Mapped[dt.datetime | None] = mapped_column(_TZ, nullable=True)
