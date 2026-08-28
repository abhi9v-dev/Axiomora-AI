# migrations

Reserved for Alembic database migrations (application DB and, in local dev,
the same instance's warehouse schema).

The Alembic environment is established in Phase 1 together with the retail
star schema (`fact_sales`, `dim_date`, `dim_store`, `dim_product`) and the
read-only warehouse role. Nothing here is used yet in Phase 0 — the `db`
service's only Phase 0 initialization is enabling the `vector` extension via
`infra/db/init.sql`.
