# migrations

Reserved for Alembic database migrations (application DB and, in local dev,
the same instance's warehouse schema).

The Alembic environment is established in Phase 1 together with the
marketplace-operations schema (`marketplace.projects`, `marketplace.task`,
`organisation.department`, `organisation.account`, and the
`analytics.v_task_lifecycle` / `analytics.v_project_status` rollup views)
and the read-only warehouse role. Nothing here is used yet in Phase 0 — the
`db` service's only Phase 0 initialization is enabling the `vector`
extension via `infra/db/init.sql`.
