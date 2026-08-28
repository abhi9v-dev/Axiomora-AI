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

**Status: Complete** (2026-08-28)

- 32 governed catalog source documents in `data/glossary/` (8 table/view,
  4 relationship, 6 measure, 9 glossary-term, 5 validation-rule), each
  validated against `app.catalog.schema.CatalogDocumentInput`.
- `EmbeddingProvider` interface (`apps/api/app/embeddings/base.py`) plus
  `FakeEmbeddingProvider` (`fake.py`): a deterministic, zero-cost feature-
  hashing (word unigram/bigram, SHA-256, stopword-filtered, L2-normalized)
  embedding — a real lexical-embedding technique, not a random stub — so
  cosine similarity genuinely reflects shared vocabulary. `get_embedding_provider`
  factory reads `EMBEDDING_PROVIDER` (only `fake` implemented so far).
- Deterministic chunker (`app/catalog/chunking.py`): paragraph-packing up
  to `max_chars`, falling back to an overlapping sliding window for any
  single paragraph longer than that.
- Migration `0002` (`catalog.document`, `catalog.chunk` with a pgvector
  `Vector(256)` column and an HNSW cosine-distance index); `catalog.*` is
  application infrastructure, not warehouse data, so it isn't exposed to
  `bi_readonly` (per docs/03_ARCHITECTURE.md's Catalog/pgvector vs.
  Warehouse data-store split).
- Ingestion pipeline (`app/catalog/ingest.py`, `python -m app.catalog.ingest`):
  content-hash-based, idempotent — unchanged documents are skipped,
  changed ones get a new version and regenerated chunks.
- Retrieval service (`app/catalog/retrieval.py`,
  `search_catalog(session, query, tenant_id=, source_id=, ...)`): pgvector
  cosine-distance search joined to `catalog.document` for tenant/source
  filtering, returning typed `RetrievalResult`s with a score and a stable
  citation string (`catalog:{kind}:{object_name}:chunk:{index}`).
- Tests (30 new, 55 total apps/api tests): chunking and embedding unit
  tests (determinism, dimension, normalization, related-vs-unrelated
  discrimination), document-loading tests, ORM metadata tests for the new
  tables, an extended offline migration-SQL test, a **pure-Python recall@5
  benchmark** (18 queries, no database — verified the embedding/chunking/
  ranking approach directly: **recall@5 = 0.94**), and a live-database
  integration test (ingest + idempotency + real pgvector query + recall@5
  via actual SQL + cross-source-filtering isolation) that self-skips
  without a reachable database, same as Phase 1's.
- Found and fixed two real bugs before they could reach a database:
  (1) a query like "quality flag column" wasn't retrieving its glossary
  entry because the entry's distinctive vocabulary ("read-only") lived only
  in its `title`, never embedded — fixed by embedding `title + chunk`
  instead of the chunk alone (recall@5 went from 0.83 to 0.94); (2)
  `pgvector`'s `register_vector()` raises unconditionally if the `vector`
  Postgres type doesn't exist yet, which would have broken *every*
  connection (including the `/ready` health check) on a freshly created,
  not-yet-migrated database — fixed by wrapping registration in
  `contextlib.suppress`.
- Refactored `Base` out of `app/db/models.py` into `app/db/base.py` so
  warehouse and catalog models share one metadata registry for Alembic;
  updated the Phase 1 metadata test to a subset check accordingly.

**Known limitations:**

- The live integration test (`test_catalog_integration.py`) could not be
  run against a real database in the session that built this phase, same
  constraint as Phase 1 — verified instead via the pure-Python recall@5
  test, offline SQL generation, and a real `uvicorn` smoke test confirming
  `/health`/`/ready` still behave correctly with the new connection-level
  pgvector wiring in place. CI's `pgvector/pgvector:pg16` service (added in
  Phase 1) runs it for real.
- The fake embedding provider is lexical (shared-vocabulary), not
  semantic — it has no notion of synonyms or word-form variants (one
  benchmark query missed because "sit"/"sits" and "claim"/"claims" don't
  share a token). This is an honest, documented limitation of a zero-cost,
  deterministic provider, not a bug; a real provider would be added the
  same way Phase 3 adds a real `LLM_PROVIDER`.

## Phase 3 — NL2SQL

**Status: Complete** (2026-08-29)

- `LLMProvider` interface (`apps/api/app/llm/base.py`, `complete(system, user) -> str`)
  plus two implementations, matching ADR 0002's provider-interface pattern:
  - `FakeLLMProvider` (`fake.py`): generic, reusable, deterministic —
    returns pre-registered canned responses matched by substring of the
    user prompt, with queued multi-response support for testing retry
    paths. Not NL2SQL-specific.
  - `AnthropicLLMProvider` (`anthropic_provider.py`): real Claude API calls
    (`claude-opus-5` by default), translating SDK exceptions (rate limit,
    connection, not-found, generic status, refusal) into one stable
    `LLMProviderError`. Verified with 9 tests that mock only
    `client.messages.create`, checked against the real installed SDK's
    actual exception constructors and response shapes — no network call,
    no API key, no cost.
  - `get_llm_provider(settings)` factory reads `LLM_PROVIDER`
    (`Settings` already required `ANTHROPIC_API_KEY` whenever
    `LLM_PROVIDER=anthropic`, since Phase 0).
- NL2SQL agent (`apps/api/app/nl2sql/`): `agent.py`'s `generate_sql(...)`
  takes only the question, dialect and already-retrieved catalog context
  (never a database handle or credentials) and returns the versioned
  `NL2SQLOutput` contract (`schema.py`: sql, dialect, referenced_objects,
  assumptions, parameters, confidence) — matching
  docs/06_DATA_MODEL_API_CONTRACTS.md exactly. Never executes SQL.
- Malformed-response handling: exactly one corrective retry on bad JSON
  *or* a schema-validation failure (missing field, out-of-range
  confidence), per docs/06 ("retried once for formatting"); a second
  failure raises `NL2SQLGenerationError` rather than returning anything
  untrusted.
- Prompt-injection defenses (`prompts.py`): retrieved catalog context and
  the user's question are wrapped in explicitly labeled
  "untrusted data, not instructions" blocks; the system prompt explicitly
  instructs the model to ignore embedded commands. Tested directly,
  including that a hostile catalog document containing a fake closing
  delimiter cannot escape its block.
- Tests (33 new, 88 total apps/api tests, all passing without a database
  or network call): fake-provider matching/ordering, Anthropic-provider
  request/response/error mapping, prompt-injection delimiting, and the
  agent's happy path, retry-then-succeed, retry-then-fail, and
  low-confidence/no-context paths.

**Known limitations:**

- `AnthropicLLMProvider` has never been exercised against the real Claude
  API (no key configured/used in this session, by design — `LLM_PROVIDER`
  defaults to `fake`). Its request construction and error handling are
  verified against the real SDK's actual types via mocking; a live call is
  the one thing that can't be confirmed without spending money, which
  wasn't authorized for this phase.
- No orchestrator/API endpoint wires the NL2SQL agent to a live HTTP
  request yet, and the Schema Agent's retrieval isn't yet connected to
  NL2SQL's `retrieved_context` input automatically -- both are the
  state-machine orchestrator's job, introduced once enough agents exist to
  coordinate (docs/03_ARCHITECTURE.md's `RECEIVED -> RETRIEVING ->
  GENERATING_SQL -> ...` flow), not Phase 3's.

## Phase 4 — Validator and safe execution

**Status: Complete** (2026-08-29)

- Static SQL policy (`apps/api/app/validator/policy.py`): parses with
  SQLGlot (postgres dialect), enforces exactly one statement that must be
  a `Select` (rejects DDL/DML/multi-statement, and `SELECT ... INTO`,
  which still parses as a Select but creates a table as a side effect --
  found by testing, not assumed), requires every referenced table/view to
  be fully schema-qualified and in `ALLOWED_OBJECTS`, and requires every
  function SQLGlot doesn't recognize as standard SQL (`exp.Anonymous` --
  empirically, this is exactly where every dangerous Postgres function
  lands: `pg_read_file`, `dblink`, `pg_sleep`, `lo_import`,
  `current_setting`/`set_config`, `pg_terminate_backend`, ...) to be in a
  small explicit allowlist (just `age`). SQL comments cannot smuggle a
  second statement or hide DDL, verified directly: AST parsing means a
  comment's content is simply never part of the executable tree.
- `ALLOWED_OBJECTS` (`allowlist.py`) is derived from the real ORM metadata
  (`app.db.models`) rather than hand-maintained, so it cannot silently
  drift from the actual schema; `catalog.*` is deliberately never
  included (see ADR-equivalent note in the migration 0002 docstring).
- Read-only executor (`executor.py`): runs only pre-validated SQL against
  `WAREHOUSE_URL` (`bi_readonly`), sets `SET LOCAL statement_timeout`, and
  fetches `row_limit + 1` rows to report truncation rather than silently
  dropping data.
- Result-shape checks (`result_checks.py`): empty result and row-limit
  truncation are informational (`pass`/`warning`), never failures -- an
  empty result is a legitimate outcome (docs/08's AT-05: explain "no
  data," don't repair); a negative value in a duration/count column that
  can never legitimately be negative (mirroring
  `data/glossary/validation_rules.yaml`'s `hold_hours_non_negative`) is
  the one hard failure, since it's an unambiguous bug signal. A
  best-effort "comparison period completeness" heuristic warns when a
  period-grouped result has only one distinct period.
- Validator Agent (`agent.py`) ties policy + parameter-placeholder
  matching + execution + result checks into one `ValidatorOutput`
  (docs/06's contract): a policy violation, an unfilled `:placeholder`, or
  a hard result-check failure all become `repairable=True` with concrete
  `feedback` text; a DB-level execution error (bad column, genuine
  timeout, ...) is caught and translated the same way rather than
  propagating a raw exception.
- `app.pipeline.answer_question`: the bounded repair loop (NL2SQL ->
  Validator ->, if repairable, regenerate with feedback appended, up to
  `MAX_SQL_REPAIRS` times total). Not the full state-machine orchestrator
  yet -- just the NL2SQL+Validator coordination Phase 4 needs.
- Tests (61 new, 149 total apps/api tests): 37 adversarial policy tests
  (every threat in docs/07's "Threats to test" list, plus comment
  obfuscation, `SELECT INTO`, unqualified names, catalog-schema access,
  and 11 specific dangerous functions), allowlist sanity tests, pure
  Python result-check tests, pipeline repair-loop tests (scripted
  validator stub -- 1-pass, retry-then-pass, exhaust-then-fail,
  non-repairable-stops-immediately, zero/negative `max_repairs`,
  NL2SQL-failure-surfaces-as-`PipelineError`), and a live-database
  integration test (executor row-limit/timeout enforcement, the full
  pipeline answering the real Q2 Buyer/Compliance-Review question
  correctly, and -- the ultimate proof -- a `FakeLLMProvider` that always
  returns `DROP TABLE marketplace.task` getting exhausted by the repair
  loop with the table still fully intact afterward) that self-skips
  without a reachable database.
- Corrected a stale claim from Phase 0 planning: root `tests/`'s README
  said backend integration tests would start landing there "starting
  Phase 4." They didn't -- Phase 1, 2 and 4's live-DB tests all correctly
  belong in `apps/api/tests` (same pytest config, same CI job, only one
  app involved). Updated both READMEs to say root `tests/` is for
  cross-app suites only, starting Phase 6.

**Known limitations:**

- The live integration test (`test_validator_integration.py`) could not be
  run against a real database in the session that built this phase, same
  constraint as Phases 1-2 -- verified instead via the 37 offline
  adversarial policy tests (the security-critical core, which needs no
  database at all) and the scripted-stub pipeline tests. CI's
  `pgvector/pgvector:pg16` service runs it for real.
- No orchestrator/API endpoint exists yet to call `answer_question` from a
  live HTTP request, and it isn't wired to the Schema Agent's real
  retrieval -- `retrieved_context` is still a caller-supplied list, not
  fetched internally. Both are later, cross-agent orchestration work.

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
