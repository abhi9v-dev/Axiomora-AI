# data/glossary

The semantic catalog's source documents: business glossary, measure
definitions, table/relationship documentation and validation-constraint
documents that the Schema Agent chunks, embeds and retrieves (see
[docs/02_SRS_SRD.md](../../docs/02_SRS_SRD.md), FR-001/FR-002/FR-003).

- `tables.yaml` — one entry per table/view (kind: `table`)
- `relationships.yaml` — foreign-key join documentation (kind: `relationship`)
- `measures.yaml` — named business measures (kind: `measure`)
- `terms.yaml` — glossary vocabulary (kind: `glossary_term`)
- `validation_rules.yaml` — business/data-quality rules (kind: `validation_rule`)
- `benchmark.yaml` — recall@5 test queries; **not** a catalog document, only
  read by `apps/api/tests/_benchmark.py`; excluded from ingestion.

Each entry in the first five files is validated against
`app.catalog.schema.CatalogDocumentInput` when loaded by
`app.catalog.documents.load_catalog_documents`. Load, chunk, embed and store
them with `python -m app.catalog.ingest` (from `apps/api`) — see the root
[README.md](../../README.md).
