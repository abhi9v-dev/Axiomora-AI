"""Recall@5 benchmark for catalog retrieval (docs/08_TEST_EVAL_ACCEPTANCE.md),
computed entirely in memory with FakeEmbeddingProvider -- no database or
pgvector required. This verifies the chunking + embedding + ranking
approach is sound; test_catalog_integration.py separately verifies the
real pgvector-backed SQL query returns equivalent results live.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.catalog.chunking import chunk_text
from app.catalog.documents import load_catalog_documents
from app.embeddings.fake import FakeEmbeddingProvider
from tests._benchmark import load_benchmark_queries

RECALL_AT_5_THRESHOLD = 0.85


@dataclass
class _IndexedChunk:
    object_name: str
    embedding: list[float]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def _build_index(provider: FakeEmbeddingProvider) -> list[_IndexedChunk]:
    """Mirrors app.catalog.ingest.ingest_catalog's embedding input exactly
    (title + chunk, not chunk alone) so this offline benchmark reflects what
    real ingestion actually stores."""
    documents = load_catalog_documents()

    index: list[_IndexedChunk] = []
    for document in documents:
        chunks = chunk_text(document.content)
        embeddings = await provider.embed([f"{document.title}\n\n{c}" for c in chunks])
        for embedding in embeddings:
            index.append(_IndexedChunk(object_name=document.object_name, embedding=embedding))
    return index


def _top_k_object_names(
    index: list[_IndexedChunk], query_embedding: list[float], k: int = 5
) -> list[str]:
    ranked = sorted(index, key=lambda c: _cosine(c.embedding, query_embedding), reverse=True)

    top_object_names: list[str] = []
    for chunk in ranked:
        if chunk.object_name not in top_object_names:
            top_object_names.append(chunk.object_name)
        if len(top_object_names) == k:
            break
    return top_object_names


async def test_recall_at_5_meets_target() -> None:
    provider = FakeEmbeddingProvider()
    index = await _build_index(provider)
    benchmark = load_benchmark_queries()
    assert len(benchmark) >= 15

    hits = 0
    misses: list[tuple[str, list[str]]] = []
    for case in benchmark:
        (query_embedding,) = await provider.embed([case.query])
        top5 = _top_k_object_names(index, query_embedding)

        if any(name in top5 for name in case.expected_object_names):
            hits += 1
        else:
            misses.append((case.query, top5))

    recall_at_5 = hits / len(benchmark)
    assert (
        recall_at_5 >= RECALL_AT_5_THRESHOLD
    ), f"recall@5={recall_at_5:.2f} below target {RECALL_AT_5_THRESHOLD}; misses={misses}"


async def test_top_result_for_an_unambiguous_query_is_the_expected_document() -> None:
    """Sanity check beyond recall alone: for a query with only one plausible
    answer, that answer should rank first, not just somewhere in the top 5."""
    provider = FakeEmbeddingProvider()
    index = await _build_index(provider)

    (query_embedding,) = await provider.embed(
        ["What is the difference between task type and task subtype?"]
    )
    top5 = _top_k_object_names(index, query_embedding)

    assert top5[0] == "task_type_vs_subtype"
