"""catalog schema: documents, chunks, pgvector embeddings

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28

Creates the governed semantic catalog (FR-001/FR-002/FR-003): `catalog.document`
holds the full, versioned source document; `catalog.chunk` holds the
embeddable pieces it was split into, each with a pgvector embedding, used
by app.catalog.retrieval for ranked, cited, tenant/source-filtered search.

This is application/catalog infrastructure, not warehouse business data, so
(unlike migration 0001's marketplace/organisation/analytics schemas) it is
not exposed to the read-only bi_readonly role -- ingestion and retrieval
both run through the normal application (DATABASE_URL) credentials, per
docs/03_ARCHITECTURE.md's "Catalog/pgvector" vs. "Warehouse" data-store
split.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Must match app.embeddings.base.EMBEDDING_DIMENSION.
EMBEDDING_DIMENSION = 256


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS catalog")

    op.create_table(
        "document",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("object_name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_id", "kind", "object_name", name="uq_document_identity"
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_document_tenant_source", "document", ["tenant_id", "source_id"], schema="catalog"
    )

    op.create_table(
        "chunk",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("catalog.document.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
        schema="catalog",
    )

    op.execute(
        "CREATE INDEX ix_chunk_embedding_hnsw ON catalog.chunk "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS catalog.ix_chunk_embedding_hnsw")
    op.drop_table("chunk", schema="catalog")
    op.drop_table("document", schema="catalog")
