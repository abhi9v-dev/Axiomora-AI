from __future__ import annotations

from app.catalog.documents import DEFAULT_GLOSSARY_DIR, load_catalog_documents


def test_loads_documents_of_every_expected_kind() -> None:
    documents = load_catalog_documents(DEFAULT_GLOSSARY_DIR)

    kinds = {d.kind for d in documents}
    assert kinds == {"table", "relationship", "measure", "glossary_term", "validation_rule"}
    assert len(documents) >= 20


def test_document_identities_are_unique() -> None:
    documents = load_catalog_documents(DEFAULT_GLOSSARY_DIR)

    identities = [(d.source_id, d.kind, d.object_name) for d in documents]
    assert len(identities) == len(set(identities))


def test_every_document_has_non_empty_title_and_content() -> None:
    documents = load_catalog_documents(DEFAULT_GLOSSARY_DIR)

    for document in documents:
        assert document.title.strip()
        assert document.content.strip()
        assert document.source_id == "marketplace_demo"


def test_key_tables_and_views_are_documented() -> None:
    documents = load_catalog_documents(DEFAULT_GLOSSARY_DIR)
    table_object_names = {d.object_name for d in documents if d.kind == "table"}

    for expected in (
        "marketplace.task",
        "marketplace.projects",
        "organisation.department",
        "organisation.account",
        "analytics.v_task_lifecycle",
        "analytics.v_project_status",
    ):
        assert expected in table_object_names
