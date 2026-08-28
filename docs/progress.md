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

## Phase 1 — Demo warehouse and semantic catalog

**Status: Not started.**

## Phase 2 — Schema retrieval service

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
