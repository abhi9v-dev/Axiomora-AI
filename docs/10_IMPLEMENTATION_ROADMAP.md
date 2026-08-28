# Step-by-Step Implementation Roadmap

Complete **one phase per session**. Do not start the next phase until the
current phase's exit criteria are met and the user has explicitly approved
moving on. See [docs/progress.md](progress.md) for current status.

## Phase 0 — Foundation

Create monorepo, Docker Compose, CI, formatting, typed settings, health
endpoints and architecture decision records.

**Exit:** one command starts web/API/database; CI is green.

## Phase 1 — Synthetic marketplace-operations warehouse

Build the marketplace-operations schema (`marketplace.projects`,
`marketplace.task`, `organisation.department`, `organisation.account`) and
the `analytics.v_task_lifecycle` / `analytics.v_project_status` rollup
views. Generate deterministic synthetic data, including a known Q2
hold-time spike in the Buyer department driven by Supplier Compliance
Review tasks. Add database migrations and a repeatable seed command. Add
tests confirming the expected business result.

**Exit:** one command (re)creates and seeds the schema; tests confirm the
known Q2 Buyer-department hold-time anomaly and its top driver.

## Phase 2 — Semantic catalog and Schema Agent

Define glossary, table, column, relationship, measure and validation
documents for the marketplace-operations schema. Add document chunking and
versioning. Implement an embedding-provider interface with a deterministic
test implementation, store embeddings in pgvector, filter by tenant/source,
and return ranked citations with retrieval scores.

**Exit:** retrieval recall@5 meets target for the benchmark terms.

## Phase 3 — NL2SQL

Add Claude provider and fake provider, structured prompts, SQL schema,
dialect configuration and benchmark harness.

**Exit:** generated SQL parses and uses only retrieved/approved objects.

## Phase 4 — Validator and safe execution

Implement SQLGlot policy, read-only executor, timeouts, row caps, domain
checks and bounded repair loop.

**Exit:** adversarial SQL never executes; benchmark execution accuracy meets
target.

## Phase 5 — Insight generation

Create compact result serialization, evidence cell IDs, narrative schema and
claim-verification pass.

**Exit:** every numeric claim is grounded; empty/failed results produce no
invented narrative.

## Phase 6 — Frontend

Build Ask, progress, clarification, answer, evidence, history and error
states with SSE.

**Exit:** Playwright completes the full question flow.

## Phase 7 — Action agent and Excel

Implement action policy, idempotency and formatted workbook with Summary,
Data, SQL & Evidence, and Validation sheets.

**Exit:** approved run downloads a correct workbook; repeat request is
idempotent.

## Phase 8 — Power BI adapter

Build interface, mock adapter and optional Entra/REST integration behind
feature flags.

**Exit:** mock tests pass; real integration only after tenant setup.

## Phase 9 — Deployment and portfolio polish

Deploy demo, add rate limits, observability, screenshots, demo video, sample
questions and security notes.

**Exit:** public demo is stable within free-tier constraints and contains
synthetic data only.

## Working rule

Complete one phase per Claude Code session. Start each session by asking
Claude to read `CLAUDE.md` plus the relevant specification, inspect existing
code, propose a small plan, implement only that phase, run tests, and update
`docs/progress.md`.

## Claude Code phase prompts

**Session bootstrap**

> Read CLAUDE.md, docs/01_PRD.md, docs/02_SRS_SRD.md, docs/03_ARCHITECTURE.md
> and docs/10_IMPLEMENTATION_ROADMAP.md. Inspect the repository. We are
> implementing Phase [N] only. First show a concise plan, affected files,
> acceptance criteria and commands you will run. Then implement, test and
> update docs/progress.md. Do not start the next phase.

**Phase 0 prompt**

> Implement Phase 0 Foundation. Create the monorepo structure, FastAPI
> health endpoint, Next.js shell, PostgreSQL/pgvector Docker Compose
> service, typed environment configuration, formatting/lint/type-check
> setup, basic CI, .env.example and setup README. Use fake external
> integrations. Acceptance: docker compose starts dependencies; API and web
> health checks work; lint/type/test commands pass.

**Phase 1 prompt**

> Implement Phase 1 only. Create the synthetic marketplace-operations schema
> (`marketplace.projects`, `marketplace.task`, `organisation.department`,
> `organisation.account`, plus the `analytics.v_task_lifecycle` /
> `analytics.v_project_status` rollup views) and deterministic seed data
> showing a Q2 hold-time spike in the Buyer department driven by Supplier
> Compliance Review tasks. Implement repeatable migrations/seeding and tests
> that assert the known business result. Do not call an LLM yet and do not
> build the glossary/catalog ingestion — that is Phase 2.

**Phase 2 prompt**

> Implement the governed catalog ingestion and retrieval service. Chunk
> table/column/relationship/glossary/measure documents, create embeddings
> through an interface with a deterministic test implementation, store in
> pgvector, filter by tenant/source, return ranked citations, and build
> recall@5 tests for benchmark questions.

**Phase 3 prompt**

> Implement NL2SQL as a typed component with Anthropic and fake providers.
> It must accept only the question, dialect and retrieved context, and
> return the versioned NL2SQL JSON contract. Add prompt-injection defenses,
> parsing/retry for malformed JSON and benchmark tests. Do not execute SQL
> in this phase.

**Phase 4 prompt**

> Implement static SQL validation, read-only execution, result checks and a
> maximum-two-attempt repair loop. Use SQLGlot, allowlists, parameterization,
> timeouts and row limits. Add adversarial tests proving DDL/DML, multiple
> statements, unknown objects and obfuscation never execute.

**Phase 5–7 prompt**

> Implement Phase [5/6/7] exactly as specified in
> docs/10_IMPLEMENTATION_ROADMAP.md. Use the contracts and security policies
> as acceptance criteria. Include deterministic tests and do not enable
> Power BI.

**Review prompt**

> Audit the current phase against its requirement IDs and acceptance tests.
> Do not implement new scope. Report gaps by severity, fix confirmed
> in-scope defects, run the full relevant test set, and update the
> traceability/progress record.
