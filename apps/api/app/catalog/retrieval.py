"""Ranked, cited, tenant/source-filtered catalog retrieval (FR-003).

Embeds the query with the same provider used at ingestion time, asks
pgvector for the nearest chunks by cosine distance, and joins back to each
chunk's parent document for tenant/source filtering and citation metadata.
The Schema Agent (Phase 3+) is the intended caller.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.schema import RetrievalResult
from app.db.catalog_models import Chunk, Document
from app.embeddings.base import EmbeddingProvider


async def search_catalog(
    session: AsyncSession,
    query: str,
    *,
    tenant_id: str,
    source_id: str,
    embedding_provider: EmbeddingProvider,
    top_k: int = 5,
) -> list[RetrievalResult]:
    (query_embedding,) = await embedding_provider.embed([query])

    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Chunk, Document, distance.label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .where(Document.tenant_id == tenant_id, Document.source_id == source_id)
        .order_by(distance)
        .limit(top_k)
    )

    rows = (await session.execute(stmt)).all()

    return [
        RetrievalResult(
            chunk_id=chunk.id,
            document_id=document.id,
            kind=document.kind,
            object_name=document.object_name,
            title=document.title,
            content=chunk.content,
            score=1.0 - distance_value,
            citation=f"catalog:{document.kind}:{document.object_name}:chunk:{chunk.chunk_index}",
        )
        for chunk, document, distance_value in rows
    ]
