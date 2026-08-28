"""Live-database integration test for Phase 2 catalog retrieval.

Skipped automatically when DATABASE_URL isn't reachable (same pattern as
test_warehouse_integration.py -- see that file for why this is one long
test function rather than several sharing a fixture). When it can run: runs
the real migrations, ingests the real glossary documents through the real
pgvector-backed pipeline, and re-runs the recall@5 benchmark through the
real SQL query (app.catalog.retrieval.search_catalog) rather than the
in-memory approximation in test_recall_offline.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.catalog.documents import load_catalog_documents
from app.catalog.ingest import ingest_catalog
from app.catalog.retrieval import search_catalog
from app.config import get_settings
from app.db.session import register_pgvector_codec
from app.embeddings.fake import FakeEmbeddingProvider
from tests._benchmark import load_benchmark_queries

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

RECALL_AT_5_THRESHOLD = 0.8


async def test_catalog_ingest_and_retrieval_end_to_end() -> None:
    settings = get_settings()
    probe_engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with probe_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip(
            "DATABASE_URL is not reachable -- run `docker compose up -d db` "
            "(see README.md) to exercise this test for real."
        )
    finally:
        await probe_engine.dispose()

    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert migration.returncode == 0, migration.stderr

    engine = create_async_engine(settings.DATABASE_URL)
    register_pgvector_codec(engine)
    try:
        embedding_provider = FakeEmbeddingProvider()
        documents = load_catalog_documents()
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            report = await ingest_catalog(session, documents, embedding_provider)
        assert report.documents_seen == len(documents)
        assert report.chunks_written > 0
        assert report.documents_created + report.documents_updated == len(documents)

        # Re-ingesting unchanged documents must be a no-op (idempotency).
        async with session_factory() as session:
            second_report = await ingest_catalog(session, documents, embedding_provider)
        assert second_report.documents_created == 0
        assert second_report.documents_updated == 0
        assert second_report.documents_unchanged == len(documents)

        benchmark = load_benchmark_queries()
        hits = 0
        async with session_factory() as session:
            for case in benchmark:
                results = await search_catalog(
                    session,
                    case.query,
                    tenant_id="default",
                    source_id="marketplace_demo",
                    embedding_provider=embedding_provider,
                    top_k=5,
                )
                assert all(0.0 <= r.score <= 1.0 for r in results)
                assert all(r.citation.startswith("catalog:") for r in results)
                object_names = [r.object_name for r in results]
                if any(name in object_names for name in case.expected_object_names):
                    hits += 1

        recall_at_5 = hits / len(benchmark)
        assert recall_at_5 >= RECALL_AT_5_THRESHOLD, f"recall@5={recall_at_5:.2f} via live pgvector"

        # Cross-source filtering: a source_id with no ingested documents
        # must return nothing, proving the WHERE clause is really applied
        # (docs/07_SECURITY_GOVERNANCE.md: "cross-tenant catalog retrieval").
        async with session_factory() as session:
            other_source_results = await search_catalog(
                session,
                "hold time",
                tenant_id="default",
                source_id="some_other_source_no_docs",
                embedding_provider=embedding_provider,
                top_k=5,
            )
        assert other_source_results == []
    finally:
        await engine.dispose()
