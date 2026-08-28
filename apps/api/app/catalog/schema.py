"""Typed contracts for the catalog: input documents and retrieval results.

Every document loaded from data/glossary/ and every retrieval response is
validated against one of these versioned Pydantic models rather than passed
around as a loose dict (architecture invariant: typed contracts).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocumentKind = Literal[
    "table", "column", "relationship", "glossary_term", "measure", "validation_rule"
]


class CatalogDocumentInput(BaseModel):
    """One source document, as loaded from data/glossary/ before ingestion."""

    tenant_id: str = "default"
    source_id: str
    kind: DocumentKind
    object_name: str
    title: str
    content: str


class RetrievalResult(BaseModel):
    """One ranked chunk returned by app.catalog.retrieval.search_catalog."""

    chunk_id: int
    document_id: int
    kind: DocumentKind
    object_name: str
    title: str
    content: str
    score: float = Field(ge=-1.0, le=1.0, description="Cosine similarity to the query.")
    citation: str
