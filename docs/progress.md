# Progress

Tracks phase-by-phase completion against
[docs/10_IMPLEMENTATION_ROADMAP.md](10_IMPLEMENTATION_ROADMAP.md). Updated at
the end of every phase.

## Phase 0 — Foundation

**Status: Complete** (2026-08-28)

- Monorepo structure created (`apps/api`, `apps/web`, `packages/contracts`,
  `data/`, `docs/`, `infra/`, `migrations/`, `tests/`).
- `docker-compose.yml` provisions PostgreSQL + pgvector (`db` service);
  `infra/db/init.sql` enables the `vector` extension.
- FastAPI backend (`apps/api`): typed `Settings` (validates required env
  vars at startup), `GET /health` (liveness) and `GET /ready` (DB
  connectivity check). 9 pytest tests passing. Ruff, Black and mypy
  (strict) all clean.
- Next.js frontend (`apps/web`, TypeScript strict + Tailwind): project shell
  at `/` rendering a `HealthStatus` component that calls the API's
  `/health` and `/ready` endpoints. 3 Vitest tests passing. ESLint,
  Prettier and `tsc --noEmit` all clean.
- `.env.example` documents every configuration variable from
  [docs/04_TRT.md](04_TRT.md) with placeholders only.
- CI workflow (`.github/workflows/ci.yml`) runs the backend and frontend
  quality gates on every push/PR.
- Two ADRs recorded: explicit state-machine orchestration
  ([0001](adr/0001-explicit-state-machine-orchestration.md)) and provider
  interfaces for external dependencies
  ([0002](adr/0002-provider-interfaces-for-external-dependencies.md)).
- Pushed to GitHub: https://github.com/abhi9v-dev/Axiomora-AI (public,
  branch `master`).

**Known limitations:**

- Docker Desktop/Engine is not installed in the development environment
  used to build this phase, so `docker compose up -d db` could not be
  executed and verified end-to-end in that session. The compose file was
  validated for syntax; a human with Docker installed must run it once to
  confirm the container starts and `/ready` reports the database as
  reachable.
- pnpm is not on `PATH` in that environment; `corepack pnpm ...` was used
  as a substitute. `corepack enable` itself failed there due to a
  permissions restriction on `C:\Program Files\nodejs` — harmless, since
  `corepack pnpm` works without it, but worth re-running `corepack enable`
  with elevated rights on a fresh machine so the plain `pnpm` command is
  available.
- No `apps/api` or `apps/web` Dockerfiles yet — containerizing those is
  explicitly Phase 9 (Deployment) scope, not Phase 0.
- `packages/contracts`, `migrations`, `data/seed`, `data/glossary` and the
  root `tests/` directory are scaffolded with explanatory READMEs only; they
  are populated starting Phase 1/2/4/6 as each phase needs them.

## Decision: demo domain changed to marketplace operations

**2026-08-28**, before Phase 1 implementation began: the demo domain was
changed from retail sales to marketplace operations (projects, tasks,
departments, accounts), replacing the retail star schema entirely. See
[ADR 0003](adr/0003-marketplace-operations-demo-domain.md) for full
context. `docs/01`–`docs/10`, `CLAUDE.md` and `README.md` were updated
accordingly; no code existed yet for the retail domain, so no code changes
were needed.

## Phase 1 — Synthetic marketplace-operations warehouse

**Status: Complete** (2026-08-28)

- ORM models (`apps/api/app/db/models.py`) for `organisation.department`,
  `organisation.account`, `marketplace.projectstage`, `projectstatus`,
  `project_sub_status`, `projects` and `task` — column names, bespoke
  lookup-table PKs (e.g. `projectstage`, not `id`) and FK structure match
  the real schema this project is modeled on (ADR 0003).
- Alembic migration `0001` (`migrations/versions/`): creates the three
  schemas, all seven tables, the three `analytics.*` rollup views
  (`v_snapshot`, `v_task_lifecycle`, `v_project_status`, ported from the
  supplied view SQL), and a `bi_readonly` role with `SELECT`-only grants
  (plus default privileges for future tables) on all three schemas.
  `alembic.ini` lives at the repo root; `migrations/env.py` runs migrations
  through the async engine so no second DB driver is needed.
- Deterministic synthetic seed generator (`apps/api/app/db/seed.py`,
  `python -m app.db.seed`): loads the real (confirmed-synthetic)
  `data/seed/organisation_department.csv` verbatim, generates 40 accounts,
  150 projects and ~1000 tasks from a fixed seed, and repeatably
  truncates+reinserts on every run. Deliberately encodes the known Phase 1
  business result: **Buyer department median task hold time spikes in Q2
  2026, driven by Supplier Onboarding / Compliance Review tasks** (~4x
  baseline on that slice, ~1.4x on the department overall) — see ADR 0003.
- Tests (`apps/api/tests/`): `test_seed_generator.py` (determinism, row
  counts, no out-of-order timestamps, the Q2 anomaly asserted directly from
  generated data — no DB needed), `test_warehouse_models.py` (ORM metadata
  sanity checks), `test_migration_offline.py` (runs `alembic upgrade head
  --sql` and checks the generated DDL — no DB needed),
  `test_warehouse_integration.py` (live end-to-end: real migration, real
  seed, queries the real view, confirms the read-only role can read but not
  write — self-skips if `DATABASE_URL` isn't reachable). 22 passed, 1
  skipped locally (no local Postgres); CI now runs a `pgvector/pgvector:pg16`
  service so the integration test executes for real there.
- Found and fixed a real bug via the pure-Python generator test before it
  ever reached a database: horizon-end timestamp clamping could push
  `startedon` before `claimedon`. Fixed by never fabricating a timestamp
  past "now" rather than clamping backward after the fact.

**Known limitations:**

- The live integration test (`test_warehouse_integration.py`) could not be
  run against a real database in the session that built this phase (no
  Docker locally — same limitation noted in Phase 0). It is verified
  offline (SQL generation) and unit-tested (generator logic) instead; run
  `docker compose up -d db && alembic upgrade head && python -m app.db.seed`
  and then `pytest` locally to exercise it for real, or check the `api` job
  in GitHub Actions, which now runs it against a real Postgres service.
- `bi_readonly`'s password is a hardcoded local/demo placeholder
  (`changeme`, matching `.env.example`), consistent with the same
  convention already used for `docker-compose.yml`'s `bi_app` user in
  Phase 0. Rotate it for any non-local deployment.

## Phase 2 — Semantic catalog and Schema Agent

**Status: Not started.**

## Phase 3 — NL2SQL

**Status: Not started.**

## Phase 4 — Validator and safe execution

**Status: Not started.**

## Phase 5 — Insight generation

**Status: Not started.**

## Phase 6 — Frontend

**Status: Not started.**

## Phase 7 — Action agent and Excel

**Status: Not started.**

## Phase 8 — Power BI adapter

**Status: Not started.**

## Phase 9 — Deployment and portfolio polish

**Status: Not started.**
