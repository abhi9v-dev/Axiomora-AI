"""Shared loader for the recall@5 benchmark query set
(data/glossary/benchmark.yaml). Test-only fixture data, not app code --
used by both test_recall_offline.py (pure Python) and
test_catalog_integration.py (live pgvector).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from app.catalog.documents import DEFAULT_GLOSSARY_DIR


class BenchmarkQuery(BaseModel):
    query: str
    expected_object_names: list[str]


def load_benchmark_queries(glossary_dir: Path = DEFAULT_GLOSSARY_DIR) -> list[BenchmarkQuery]:
    path = glossary_dir / "benchmark.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [BenchmarkQuery.model_validate(entry) for entry in raw]
