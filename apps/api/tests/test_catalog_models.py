"""Sanity checks on the catalog ORM models -- pure metadata introspection,
no database connection needed.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import UniqueConstraint

import app.db.catalog_models  # noqa: F401  (registers catalog.* tables on Base.metadata)
from app.db.base import Base
from app.embeddings.base import EMBEDDING_DIMENSION

EXPECTED_TABLES = {"catalog.document", "catalog.chunk"}


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables.keys()) >= EXPECTED_TABLES


def test_chunk_document_id_references_document() -> None:
    chunk = Base.metadata.tables["catalog.chunk"]
    fk_targets = {fk.target_fullname for fk in chunk.foreign_keys}

    assert "catalog.document.id" in fk_targets


def test_chunk_embedding_column_dimension_matches_embedding_provider() -> None:
    chunk = Base.metadata.tables["catalog.chunk"]
    embedding_type = chunk.columns["embedding"].type

    assert isinstance(embedding_type, Vector)
    assert embedding_type.dim == EMBEDDING_DIMENSION


def test_document_identity_columns_are_unique_together() -> None:
    document = Base.metadata.tables["catalog.document"]
    unique_column_sets = [
        {c.name for c in constraint.columns}
        for constraint in document.constraints
        if isinstance(constraint, UniqueConstraint)
    ]

    assert {"tenant_id", "source_id", "kind", "object_name"} in unique_column_sets
