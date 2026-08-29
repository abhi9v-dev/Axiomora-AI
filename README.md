# NL-to-Insight BI Copilot

A governance-safe, multi-agent BI Copilot: ask a natural-language business
question (e.g. *"Why did median task hold time spike for the Buyer
department in Q2?"*) and get back a verified, evidence-grounded answer —
retrieved schema context, validated read-only SQL, checked results, a
plain-English insight with citations, and an exportable Excel workbook.

The demo domain is **marketplace operations**: projects, tasks, departments
and accounts flowing through a workflow engine, with analytics views over
task lifecycle timing (claim wait, hold time, SLA breaches) and project
health (stuck/unclaimed detection). All seed data is synthetic — modeled on
a real schema, populated with fabricated rows.

Full product, architecture, security and roadmap specifications live in
[`docs/`](docs/); start with [`CLAUDE.md`](CLAUDE.md).

**Status:** Phase 0 (Foundation), Phase 1 (Synthetic marketplace-operations
warehouse), Phase 2 (Semantic catalog and Schema Agent retrieval), Phase 3
(NL2SQL agent), Phase 4 (Validator Agent and safe execution), Phase 5
(Insight generation) and Phase 6 (Frontend) complete. See
[docs/progress.md](docs/progress.md) for phase-by-phase status.

## Prerequisites

| Tool                        | Version   | Notes                                                        |
| ---------------------------- | --------- | --------------------------------------------------------------- |
| Git                          | 2.4+      |                                                                  |
| Docker Desktop/Engine        | with Compose v2 | Runs PostgreSQL + pgvector locally.                        |
| Python                       | 3.12+     |                                                                  |
| Node.js                      | 22 LTS    |                                                                  |
| pnpm                         | latest    | Enable via Corepack (bundled with Node ≥ 16.10): `corepack enable`. If that fails with a permissions error, use `corepack pnpm <command>` in place of `pnpm <command>` everywhere below. |
| Claude Code CLI               | —         | Only needed if you're driving development through Claude Code itself. |

## First-time setup

```bash
git clone <this-repo>
cd bi-copilot

# 1. Environment files (never commit the real .env files)
cp .env.example apps/api/.env
cp .env.example apps/web/.env.local   # only NEXT_PUBLIC_* vars are actually read by Next.js

# 2. Start PostgreSQL + pgvector
docker compose up -d db
docker compose ps   # wait for "healthy"

# 3. Backend
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# 4. Create the warehouse schema (run from the repo root, where alembic.ini lives)
cd ../..                  # back to bi-copilot/
alembic upgrade head

# 5. Load deterministic synthetic warehouse data (run from apps/api)
cd apps/api
python -m app.db.seed

# 6. Ingest the semantic catalog (glossary/table/measure docs -> pgvector)
python -m app.catalog.ingest

uvicorn app.main:app --reload --port 8000
```

Re-running `python -m app.db.seed` or `python -m app.catalog.ingest` is
safe and expected — the seed script truncates and reinserts the same
deterministic rows every time, and the catalog ingester only re-embeds a
document whose content actually changed since the last run.

In a second terminal:

```bash
cd bi-copilot/apps/web
pnpm install   # installs the whole pnpm workspace (apps/*, packages/*, tests/e2e)
pnpm dev   # http://localhost:3000
```

Open http://localhost:3000/ask to ask a question, or http://localhost:3000
for the backend-status shell. With the default `LLM_PROVIDER=fake`, only
one question is actually answerable end to end — *"Why did median task
hold time spike for the Buyer department in Q2?"* (the first sample
question on the Ask page) — since `app.llm.demo` only scripts that one
canonical, deliberately-seeded scenario; any other question will complete
the flow (progress, then a clear failure state) but won't produce a real
answer without `LLM_PROVIDER=anthropic` and a real `ANTHROPIC_API_KEY`.

## Everyday commands

| Task                       | Command (from the given directory)                    |
| ----------------------------- | ---------------------------------------------------------- |
| Apply database migrations       | repo root: `alembic upgrade head`                              |
| Roll back the last migration     | repo root: `alembic downgrade -1`                              |
| Reseed synthetic warehouse data   | `apps/api`: `python -m app.db.seed` (repeatable/idempotent)   |
| Ingest/refresh the semantic catalog | `apps/api`: `python -m app.catalog.ingest` (repeatable/idempotent) |
| Run API dev server              | `apps/api`: `uvicorn app.main:app --reload --port 8000`      |
| Run API tests                   | `apps/api`: `pytest`                                          |
| Lint/format/type-check API       | `apps/api`: `ruff check .` · `black --check .` · `mypy app tests` |
| Run web dev server               | `apps/web`: `pnpm dev`                                         |
| Run web tests                    | `apps/web`: `pnpm test`                                        |
| Lint/format/type-check web        | `apps/web`: `pnpm lint` · `pnpm format` · `pnpm typecheck`      |
| Production web build              | `apps/web`: `pnpm build`                                       |
| Run the Playwright E2E suite (needs both servers running, see `tests/e2e/README.md`) | `tests/e2e`: `pnpm exec playwright install --with-deps chromium` (once) then `pnpm test` |
| Stop the database                 | repo root: `docker compose down` (add `-v` to also wipe local data) |

## Verifying the backend directly

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/ready
# {"status":"ready","checks":{"database":"ok"}}                (db reachable)
# {"status":"not_ready","checks":{"database":"error: ..."}}    (db unreachable, HTTP 503)
```

## Configuration

All configuration is environment-driven — see [`.env.example`](.env.example)
for the full list with placeholder values, and
[docs/04_TRT.md](docs/04_TRT.md#configuration-contract) for the rationale.
Nothing in this repository requires a paid API key: `LLM_PROVIDER=fake` and
`EMBEDDING_PROVIDER=fake` (the defaults) use deterministic, zero-cost local
providers. Setting `LLM_PROVIDER=anthropic` (with a real `ANTHROPIC_API_KEY`)
switches the NL2SQL agent to real, metered Claude API calls — this is
opt-in and never free; see [docs/04_TRT.md](docs/04_TRT.md#cost-strategy).
`POWER_BI_ENABLED` defaults to `false` and must stay that way outside an
explicitly configured, licensed tenant (Phase 8). `RETRIEVAL_MIN_SCORE`
and `NL2SQL_MIN_CONFIDENCE` control when a run pauses at
`NEEDS_CLARIFICATION` instead of guessing (Phase 6's orchestrator,
`app.orchestrator.service`).

The API's typed `Settings` (`apps/api/app/config.py`) validates required
variables at startup and fails fast — for example, it refuses to start with
`LLM_PROVIDER=anthropic` and no `ANTHROPIC_API_KEY`.

## Repository structure

```
bi-copilot/
├── CLAUDE.md              Project instructions for Claude Code sessions
├── docker-compose.yml     PostgreSQL + pgvector (local dev)
├── pnpm-workspace.yaml    pnpm workspace root (apps/*, packages/*, tests/e2e)
├── apps/
│   ├── api/               FastAPI backend (Python 3.12, Pydantic v2, SQLAlchemy 2 async)
│   └── web/                Next.js frontend (TypeScript strict, Tailwind CSS)
├── alembic.ini              Alembic entrypoint config (points at /migrations)
├── packages/contracts/     TypeScript mirrors of the backend's run/agent contracts (Phase 6+)
├── data/seed/               Synthetic marketplace-operations seed data + generator fixtures
├── data/glossary/            Semantic catalog source docs (tables/relationships/measures/terms/rules)
├── docs/                      Product, architecture, security, roadmap specs + ADRs
├── infra/                      Local/deployment infra config (DB init script, etc.)
├── migrations/                  Alembic migration scripts (warehouse schema + catalog/pgvector + runs)
└── tests/e2e/                    Playwright E2E suite driving the real frontend + backend (Phase 6+)
```

## Known limitations

- The API and web apps are not containerized — that's Phase 9 scope.
  `docker-compose.yml` currently runs only the database.
- `EMBEDDING_PROVIDER` only supports `fake` so far (a deterministic
  feature-hashing embedding, not a stub — see
  `apps/api/app/embeddings/fake.py`); a real provider would be a later,
  separate addition, the same pattern `LLM_PROVIDER=anthropic` follows for
  the NL2SQL agent (Phase 3).
- The warehouse schema targets PostgreSQL only, per the project's MVP
  constraint — no other SQL dialects are supported.
- The orchestrator (`app.orchestrator`) is single-process: its SSE event
  buses and background-task registry live in process memory
  (`app.orchestrator.events`, `app.api.runs`), so it assumes exactly one
  API worker. Moving to more than one would need a real pub/sub (e.g.
  Postgres `LISTEN`/`NOTIFY` or Redis) in place of the in-memory bus —
  fine for this project's single-instance MVP deployment (Phase 9), not
  assumed silently.
- A run's persisted state (`runs.run`) is one JSONB-heavy table rather
  than docs/06_DATA_MODEL_API_CONTRACTS.md's fully normalized
  `run`/`sql_attempt`/`validation`/`query_result`/`insight` entities — see
  `apps/api/app/db/run_models.py`'s docstring for the rationale. Nothing
  today needs to query attempts/checks/results across runs relationally.
- Only one demo source/tenant exists (`marketplace_demo`/`default`, see
  `app.api.runs`) — there's no auth or multi-tenant source selection yet
  (no phase in the roadmap adds one), so the Ask page has no source
  selector.
- With the default `LLM_PROVIDER=fake`, only the one canonical seeded
  question is actually answerable end to end (`apps/api/app/llm/demo.py`)
  — any other question completes the flow but fails at NL2SQL generation,
  by design (a bare `FakeLLMProvider` has no other scripted responses).
- The Playwright E2E suite (`tests/e2e`) could not be run against real
  servers in the session that built Phase 6 — no Docker/Postgres in that
  environment, same constraint as every other live-database test in this
  project. `playwright test --list` was used to verify the suite parses;
  CI's `e2e` job runs it for real, end to end, against a real Postgres
  service.
