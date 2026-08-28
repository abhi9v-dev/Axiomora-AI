"""SQLAlchemy 2 ORM models for the governed semantic catalog (pgvector).

Two tables: `catalog.document` is the full, versioned source document
(one row per table/column/relationship/glossary-term/measure/validation-rule
entry ingested from data/glossary/); `catalog.chunk` holds the embeddable
pieces a document was split into, each with its own vector. Retrieval
queries `catalog.chunk` and joins back to `catalog.document` for citation
metadata and tenant/source filtering (see app.catalog.retrieval).
"""

from __future__ import annotations

import datetime as dt

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.embeddings.base import EMBEDDING_DIMENSION

_TZ = DateTime(timezone=True)


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_id", "kind", "object_name", name="uq_document_identity"
        ),
        {"schema": "catalog"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    object_name: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(_TZ, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        _TZ, server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    __tablename__ = "chunk"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
        {"schema": "catalog"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("catalog.document.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION))
    created_at: Mapped[dt.datetime] = mapped_column(_TZ, server_default=func.now())
