"""Loads catalog source documents from data/glossary/*.yaml.

Pure I/O and validation -- no database or embedding provider calls here,
so this can be (and is) unit tested without any external dependency.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.catalog.schema import CatalogDocumentInput

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_GLOSSARY_DIR = REPO_ROOT / "data" / "glossary"

# benchmark.yaml has a different shape (query/expected_object_names) and is
# loaded separately by tests, not as a catalog document.
_EXCLUDED_FILENAMES = {"benchmark.yaml"}


def load_catalog_documents(glossary_dir: Path = DEFAULT_GLOSSARY_DIR) -> list[CatalogDocumentInput]:
    documents: list[CatalogDocumentInput] = []
    seen: set[tuple[str, str, str]] = set()

    for path in sorted(glossary_dir.glob("*.yaml")):
        if path.name in _EXCLUDED_FILENAMES:
            continue

        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        for entry in raw:
            document = CatalogDocumentInput.model_validate(entry)
            identity = (document.source_id, document.kind, document.object_name)
            if identity in seen:
                raise ValueError(f"Duplicate catalog document identity {identity} in {path.name}")
            seen.add(identity)
            documents.append(document)

    return documents
