"""EmbeddingProvider interface.

Keeps the embedding model separated from catalog ingestion/retrieval code
(ADR 0002: provider interfaces for external dependencies), so a real
provider (e.g. Voyage AI) can be swapped in later purely by adding a new
implementation and an EMBEDDING_PROVIDER config value -- no other code
changes.
"""

from __future__ import annotations

from typing import Protocol

# Shared by every provider and by the pgvector column definition
# (app.db.catalog_models.Chunk.embedding) -- all embeddings in this system
# have this many dimensions regardless of which provider produced them.
EMBEDDING_DIMENSION = 256


class EmbeddingProvider(Protocol):
    """Turns text into fixed-length vectors for pgvector similarity search."""

    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning one vector per input, in order."""
        ...
