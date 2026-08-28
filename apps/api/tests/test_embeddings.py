from __future__ import annotations

import math

import pytest

from app.config import Settings
from app.embeddings.base import EMBEDDING_DIMENSION
from app.embeddings.factory import get_embedding_provider
from app.embeddings.fake import FakeEmbeddingProvider


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_embeddings_have_expected_dimension_and_are_normalized() -> None:
    provider = FakeEmbeddingProvider()
    (vector,) = await provider.embed(["Hold time is the duration a task sits with its assignee."])

    assert len(vector) == EMBEDDING_DIMENSION
    norm = math.sqrt(sum(v * v for v in vector))
    assert abs(norm - 1.0) < 1e-9


async def test_empty_text_yields_zero_vector() -> None:
    provider = FakeEmbeddingProvider()
    (vector,) = await provider.embed([""])

    assert vector == [0.0] * EMBEDDING_DIMENSION


async def test_embeddings_are_deterministic_across_calls() -> None:
    provider = FakeEmbeddingProvider()
    text = "Median hold time for the Buyer department spiked in Q2."

    first = await provider.embed([text])
    second = await provider.embed([text])

    assert first == second


async def test_embeddings_are_deterministic_across_instances() -> None:
    text = "Supplier Compliance Review tasks in the Buyer department."

    first = await FakeEmbeddingProvider().embed([text])
    second = await FakeEmbeddingProvider().embed([text])

    assert first == second


async def test_related_texts_are_more_similar_than_unrelated_ones() -> None:
    provider = FakeEmbeddingProvider()
    texts = [
        "Hold time is the duration a task sits with its assignee before completion.",
        "What does hold time mean for a task?",
        "Completely unrelated sentence about cats and dogs playing outside.",
    ]
    hold_time_def, hold_time_question, unrelated = await provider.embed(texts)

    related_similarity = _cosine(hold_time_def, hold_time_question)
    unrelated_similarity = _cosine(hold_time_def, unrelated)

    assert related_similarity > unrelated_similarity
    assert related_similarity > 0.3
    assert unrelated_similarity < 0.15


async def test_batch_embed_matches_individual_embed_calls() -> None:
    provider = FakeEmbeddingProvider()
    texts = ["First text about tasks.", "Second text about departments."]

    batched = await provider.embed(texts)
    individually = [
        (await provider.embed([texts[0]]))[0],
        (await provider.embed([texts[1]]))[0],
    ]

    assert batched == individually


def test_factory_returns_fake_provider_for_fake_setting() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        EMBEDDING_PROVIDER="fake",
    )

    provider = get_embedding_provider(settings)

    assert isinstance(provider, FakeEmbeddingProvider)


def test_factory_rejects_unsupported_provider() -> None:
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/app",
        WAREHOUSE_URL="postgresql+asyncpg://u:p@localhost:5432/wh",
        EMBEDDING_PROVIDER="not-a-real-provider",
    )

    with pytest.raises(ValueError, match="not-a-real-provider"):
        get_embedding_provider(settings)
