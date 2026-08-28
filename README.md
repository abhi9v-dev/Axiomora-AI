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
(NL2SQL agent) and Phase 4 (Validator Agent and safe execution) complete.
See [docs/progress.md](docs/progress.md) for phase-by-phase status.

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
pnpm install
pnpm dev   # http://localhost:3000
```

Open http://localhost:3000 — the page shell shows a "Backend status" card
that calls the API's `/health` and `/ready` endpoints.

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
explicitly configured, licensed tenant (Phase 8).

The API's typed `Settings` (`apps/api/app/config.py`) validates required
variables at startup and fails fast — for example, it refuses to start with
`LLM_PROVIDER=anthropic` and no `ANTHROPIC_API_KEY`.

## Repository structure

```
bi-copilot/
├── CLAUDE.md              Project instructions for Claude Code sessions
├── docker-compose.yml     PostgreSQL + pgvector (local dev)
├── apps/
│   ├── api/               FastAPI backend (Python 3.12, Pydantic v2, SQLAlchemy 2 async)
│   └── web/                Next.js frontend (TypeScript strict, Tailwind CSS)
├── alembic.ini              Alembic entrypoint config (points at /migrations)
├── packages/contracts/     Reserved for contracts shared with the frontend (from Phase 6)
├── data/seed/               Synthetic marketplace-operations seed data + generator fixtures
├── data/glossary/            Semantic catalog source docs (tables/relationships/measures/terms/rules)
├── docs/                      Product, architecture, security, roadmap specs + ADRs
├── infra/                      Local/deployment infra config (DB init script, etc.)
├── migrations/                  Alembic migration scripts (warehouse schema + catalog/pgvector)
└── tests/                        Cross-app E2E suites (from Phase 6; backend integration tests live in apps/api/tests)
```

## Known limitations

- The API and web apps are not containerized — that's Phase 9 scope.
  `docker-compose.yml` currently runs only the database.
- `packages/contracts` and the root `tests/` directory are still
  placeholders (with READMEs explaining what arrives when) — each agent's
  contracts live beside it (e.g. `apps/api/app/nl2sql/schema.py`) until a
  contract genuinely needs to be shared with the TypeScript frontend too
  (expected around Phase 6).
- `EMBEDDING_PROVIDER` only supports `fake` so far (a deterministic
  feature-hashing embedding, not a stub — see
  `apps/api/app/embeddings/fake.py`); a real provider would be a later,
  separate addition, the same pattern `LLM_PROVIDER=anthropic` follows for
  the NL2SQL agent (Phase 3).
- The warehouse schema targets PostgreSQL only, per the project's MVP
  constraint — no other SQL dialects are supported.
- No orchestrator/API endpoint calls `app.pipeline.answer_question` from a
  live HTTP request yet, and it isn't wired to the Schema Agent's real
  retrieval (`retrieved_context` is still a caller-supplied list) — both
  are the state-machine orchestrator's job once enough agents exist to
  coordinate.
