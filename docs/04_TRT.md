# Technical Requirements & Technology Rationale (TRT)

## Selected stack

| Layer         | Choice                                                    | Rationale                                                     |
| ------------- | ----------------------------------------------------------- | ---------------------------------------------------------------- |
| Web           | Next.js + TypeScript + Tailwind                              | Strong typed UI, streaming support, simple deployment             |
| API           | FastAPI + Pydantic v2                                        | Typed contracts, async endpoints, generated OpenAPI                |
| Orchestration | Explicit Python state machine                                | Debuggable, bounded workflow; Claude Code alignment                |
| LLM           | Claude behind `LLMProvider`                                  | Provider can be mocked for deterministic, zero-cost tests           |
| Retrieval     | PostgreSQL + pgvector                                        | One free/open database for metadata and vectors                    |
| SQL parser    | SQLGlot                                                       | Dialect-aware AST inspection and normalization                      |
| Warehouse     | PostgreSQL                                                    | Free, familiar and sufficient for MVP                                |
| Excel         | openpyxl / xlsxwriter                                         | Formatted workbook output                                           |
| Testing       | pytest, Testcontainers, Playwright                            | Unit, integration and end-to-end coverage                            |
| Packaging     | Docker Compose                                                | Reproducible local setup                                             |

## Required developer software

- Git 2.4+
- Docker Desktop/Engine with Compose v2
- Python 3.12+
- Node.js 22 LTS and pnpm
- Claude Code CLI with an authenticated supported account

## Configuration contract

```
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://...
WAREHOUSE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=...
LLM_PROVIDER=anthropic
LLM_MODEL=<configured Claude model>
EMBEDDING_PROVIDER=<configured provider or local model>
MAX_SQL_REPAIRS=2
QUERY_TIMEOUT_MS=10000
QUERY_ROW_LIMIT=5000
POWER_BI_ENABLED=false
```

Never commit real secret values. `.env.example` (repo root) documents every
variable with a placeholder; the API's typed `Settings` (`apps/api/app/config.py`)
validates required variables at startup and fails fast if they are missing
or inconsistent (e.g. `LLM_PROVIDER=anthropic` without `ANTHROPIC_API_KEY`).

## Quality gates

- Ruff/Black and mypy (strict) for Python.
- ESLint/Prettier and strict TypeScript for the frontend.
- Conventional migrations; no schema changes at runtime.
- ≥ 80% unit coverage on policy, validators and contracts (from Phase 4
  onward, once those modules exist).
- Contract tests for every agent boundary (from Phase 3 onward).
- Dependency and secret scanning in CI.

## Cost strategy

- Run PostgreSQL/pgvector and all services locally for zero hosting cost.
- Use a deterministic fake LLM (`LLM_PROVIDER=fake`) for tests and UI
  development.
- Use a local/deterministic embedding provider where practical
  (`EMBEDDING_PROVIDER=fake` in development).
- Treat hosted LLM calls as metered even when a temporary free allowance
  exists.
- Keep deployment adapters portable because free-tier offerings change.
