"""Catalog ingestion pipeline: load documents, chunk, embed, upsert.

Idempotent and safe to re-run: a document's content hash determines whether
it needs a new version and regenerated chunks; unchanged documents are
skipped entirely, so citations stay stable across repeated ingestion runs.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.catalog.chunking import chunk_text
from app.catalog.documents import load_catalog_documents
from app.catalog.schema import CatalogDocumentInput
from app.config import get_settings
from app.db.catalog_models import Chunk, Document
from app.db.session import get_engine
from app.embeddings.base import EmbeddingProvider
from app.embeddings.factory import get_embedding_provider


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class IngestReport:
    documents_seen: int = 0
    documents_created: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    chunks_written: int = 0


async def ingest_catalog(
    session: AsyncSession,
    documents: list[CatalogDocumentInput],
    embedding_provider: EmbeddingProvider,
) -> IngestReport:
    report = IngestReport(documents_seen=len(documents))

    for doc_input in documents:
        new_hash = content_hash(doc_input.content)

        existing = await session.scalar(
            select(Document).where(
                Document.tenant_id == doc_input.tenant_id,
                Document.source_id == doc_input.source_id,
                Document.kind == doc_input.kind,
                Document.object_name == doc_input.object_name,
            )
        )

        if existing is not None and existing.content_hash == new_hash:
            report.documents_unchanged += 1
            continue

        chunk_contents = chunk_text(doc_input.content)
        # Embed title + chunk (not the chunk alone): titles carry distinctive
        # vocabulary ("... is read-only") that meaningfully improves
        # retrieval; the stored chunk content itself stays title-free since
        # RetrievalResult already surfaces the title as its own field.
        embeddings = await embedding_provider.embed(
            [f"{doc_input.title}\n\n{chunk}" for chunk in chunk_contents]
        )

        if existing is None:
            document = Document(
                tenant_id=doc_input.tenant_id,
                source_id=doc_input.source_id,
                kind=doc_input.kind,
                object_name=doc_input.object_name,
                title=doc_input.title,
                content=doc_input.content,
                content_hash=new_hash,
                version=1,
            )
            session.add(document)
            report.documents_created += 1
        else:
            document = existing
            document.title = doc_input.title
            document.content = doc_input.content
            document.content_hash = new_hash
            document.version += 1
            await session.execute(delete(Chunk).where(Chunk.document_id == document.id))
            report.documents_updated += 1

        await session.flush()  # assigns document.id for newly-added rows

        for index, (chunk_content, embedding) in enumerate(
            zip(chunk_contents, embeddings, strict=True)
        ):
            session.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=index,
                    content=chunk_content,
                    embedding=embedding,
                )
            )
            report.chunks_written += 1

    await session.commit()
    return report


async def _main() -> None:
    settings = get_settings()
    engine = get_engine()
    embedding_provider = get_embedding_provider(settings)
    documents = load_catalog_documents()

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        report = await ingest_catalog(session, documents, embedding_provider)

    print(
        f"Ingested {report.documents_seen} documents: {report.documents_created} created, "
        f"{report.documents_updated} updated, {report.documents_unchanged} unchanged, "
        f"{report.chunks_written} chunks written."
    )


if __name__ == "__main__":
    asyncio.run(_main())
