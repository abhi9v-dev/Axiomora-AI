"""Selects an EmbeddingProvider implementation from Settings.EMBEDDING_PROVIDER.

Only "fake" is implemented so far -- Phase 2 scope is the interface plus a
deterministic test implementation (see docs/10_IMPLEMENTATION_ROADMAP.md).
A real provider is added the same way LLM_PROVIDER gained "anthropic" in
Phase 3: a new module implementing EmbeddingProvider, wired in here.
"""

from __future__ import annotations

from app.config import Settings
from app.embeddings.base import EmbeddingProvider
from app.embeddings.fake import FakeEmbeddingProvider


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.EMBEDDING_PROVIDER == "fake":
        return FakeEmbeddingProvider()
    raise ValueError(
        f"Unsupported EMBEDDING_PROVIDER={settings.EMBEDDING_PROVIDER!r}. "
        "Only 'fake' is implemented; set EMBEDDING_PROVIDER=fake."
    )
