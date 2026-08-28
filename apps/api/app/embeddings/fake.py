"""Deterministic, zero-cost embedding provider for development and tests.

Uses the "hashing trick" (feature hashing): word unigrams and bigrams are
hashed into a fixed-size vector with SHA-256 (never Python's built-in
`hash()`, which is randomized per process and would break determinism
across runs), term-frequency weighted, then L2-normalized. This is a real,
long-established lexical-embedding technique (e.g. scikit-learn's
HashingVectorizer) -- not a random stub -- so cosine similarity between
vectors genuinely reflects shared vocabulary between two texts, which is
enough to exercise and benchmark the retrieval pipeline without any ML
model, network call, or paid API.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.embeddings.base import EMBEDDING_DIMENSION

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Common English function words carry little lexical-similarity signal and
# would otherwise inflate the similarity of two unrelated texts just for
# sharing "the"/"is"/"a". Filtering them sharpens the hashing-trick vectors
# without needing corpus-level IDF statistics.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "for",
        "in",
        "on",
        "at",
        "to",
        "from",
        "by",
        "with",
        "without",
        "into",
        "onto",
        "over",
        "under",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "where",
        "while",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "itself",
        "you",
        "your",
        "yours",
        "we",
        "our",
        "ours",
        "they",
        "their",
        "theirs",
        "he",
        "she",
        "his",
        "her",
        "him",
        "not",
        "no",
        "nor",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "would",
        "should",
        "could",
        "may",
        "might",
        "must",
        "shall",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "any",
        "because",
        "before",
        "below",
        "between",
        "both",
        "down",
        "during",
        "each",
        "few",
        "further",
        "here",
        "how",
        "i",
        "just",
        "more",
        "most",
        "once",
        "only",
        "other",
        "out",
        "own",
        "s",
        "same",
        "t",
        "up",
    ]
)


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def _stable_hash(feature: str) -> int:
    digest = hashlib.sha256(feature.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _embed_one(text: str, dimension: int) -> list[float]:
    tokens = _tokenize(text)
    bigrams = [f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False)]

    vector = [0.0] * dimension
    for feature in [*tokens, *bigrams]:
        index = _stable_hash(feature) % dimension
        vector[index] += 1.0

    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


class FakeEmbeddingProvider:
    """Deterministic embedding provider; see module docstring."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embed_one(text, self.dimension) for text in texts]
