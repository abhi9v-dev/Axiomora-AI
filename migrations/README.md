# migrations

Alembic migrations for the application database and, in local dev, the same
instance's warehouse and catalog schemas. Run from the repo root (where
`alembic.ini` lives): `alembic upgrade head` / `alembic downgrade -1`.

- `0001_marketplace_operations_schema.py` (Phase 1) — the
  marketplace-operations warehouse tables (`marketplace.projects`,
  `marketplace.task`, `organisation.department`, `organisation.account`,
  the lookup tables), the `analytics.v_snapshot` / `v_task_lifecycle` /
  `v_project_status` rollup views, and the read-only `bi_readonly` role.
- `0002_catalog_pgvector.py` (Phase 2) — the governed semantic catalog
  (`catalog.document`, `catalog.chunk` with a pgvector embedding column and
  an HNSW cosine-distance index); enables the `vector` extension itself as
  a safety net, though `infra/db/init.sql` already does so at container
  first-init.

`env.py` imports the ORM models from `apps/api/app/db/{models,catalog_models}.py`
by path (this directory is a sibling of `apps/`, not nested inside
`apps/api`) and runs migrations through the async engine, so no second,
synchronous database driver is needed.
