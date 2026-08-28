# CLAUDE.md — NL-to-Insight BI Copilot

## Mission

Build a trustworthy NL-to-Insight BI Copilot. Correctness, safety, evidence and
reproducibility take priority over demo theatrics.

This repository implements the product described in
[docs/01_PRD.md](docs/01_PRD.md): a governance-safe, five-agent pipeline that
turns a natural-language business question into a verified, evidence-grounded
answer, and optionally exports or publishes that answer as an approved
artifact.

## Session bootstrap

Every working session on this repository should start with:

> Read CLAUDE.md, docs/01_PRD.md, docs/02_SRS_SRD.md, docs/03_ARCHITECTURE.md
> and docs/10_IMPLEMENTATION_ROADMAP.md. Inspect the repository. We are
> implementing Phase [N] only. First show a concise plan, affected files,
> acceptance criteria and commands you will run. Then implement, test and
> update docs/progress.md. Do not start the next phase.

Phase-specific prompts are catalogued in
[docs/10_IMPLEMENTATION_ROADMAP.md](docs/10_IMPLEMENTATION_ROADMAP.md).

## Required behavior

- Read the relevant files in `/docs` before changing code.
- Inspect the repository; do not assume a file or dependency exists.
- Propose a concise plan and name the files you will change.
- Work only on the requested roadmap phase.
- Preserve existing user changes and avoid unrelated refactors.
- Add or update tests with every behavior change.
- Run formatting, linting, typing and relevant tests before declaring a phase
  complete.
- Summarize changes, tests, known limitations and the exact next step.

## Architecture invariants

These hold for every phase, not just the one currently being implemented:

- Agents are bounded, typed components coordinated by an explicit state
  machine — never an unconstrained agent-to-agent conversation.
- The language model never receives credentials or direct database/action
  access.
- Warehouse access is read-only, through a dedicated read-only role.
- SQL must pass AST parsing and policy checks before execution.
- Failed validation blocks the Insight Agent and the Action Agent.
- Numeric narrative claims require result-cell evidence references.
- External actions require policy checks, explicit user approval and
  idempotency keys.
- No secrets or production personal data in code, tests, prompts or logs.
- Synthetic data only — no real personal information anywhere in this
  repository. The demo domain is marketplace operations (projects, tasks,
  departments, accounts), modeled on a real schema but populated entirely
  with fabricated rows.

## Coding standards

- Backend: Python 3.12+, FastAPI, Pydantic v2, async SQLAlchemy 2, explicit
  type hints, mypy strict.
- Frontend: TypeScript strict mode, accessible React components.
- Small modules and dependency-injected interfaces for the LLM, embeddings,
  warehouse access and action destinations, so every external dependency can
  be swapped for a deterministic fake in tests.
- Structured errors with stable codes; never leak raw stack traces to
  clients.
- Database schema changes go through migrations — no runtime schema changes.
- Prefer deterministic tests; fake external services by default
  (`LLM_PROVIDER=fake`, `EMBEDDING_PROVIDER=fake`).

## Definition of done (per phase)

- The phase's acceptance criteria (see
  [docs/10_IMPLEMENTATION_ROADMAP.md](docs/10_IMPLEMENTATION_ROADMAP.md)) are
  met.
- Tests cover happy, error and security paths relevant to the phase.
- Lint, format, type-check and test commands pass locally, or failures are
  reported precisely.
- Documentation and `.env.example` reflect any configuration changes.
- No TODO silently substitutes for a required feature.
- [docs/progress.md](docs/progress.md) is updated.

## Prohibited shortcuts

- Executing model-generated SQL without parsing and policy checks.
- Letting the model perform calculations that can be deterministic (SQL or
  Python instead).
- Creating a narrative after validation failure.
- Hard-coding secrets, or claiming the Claude API or Power BI operations are
  free.
- Enabling Power BI mutations by default (`POWER_BI_ENABLED` must default to
  `false`).

## Repository map

```
bi-copilot/
├── apps/api/      FastAPI backend (Python 3.12, Pydantic v2, SQLAlchemy 2 async)
├── apps/web/      Next.js frontend (TypeScript strict, Tailwind CSS)
├── packages/contracts/  Versioned cross-language contracts (introduced as agents need them)
├── data/seed/     Deterministic synthetic marketplace-operations seed data (Phase 1+)
├── data/glossary/ Business glossary / semantic catalog source documents (Phase 2+)
├── docs/          Product, architecture, security and roadmap specifications
├── infra/         Local/deployment infrastructure config (Docker init scripts, later IaC)
├── migrations/    Alembic database migrations (introduced in Phase 1)
└── tests/         Cross-cutting integration/E2E suites (introduced from Phase 4/6)
```

## Current status

See [docs/progress.md](docs/progress.md) for the authoritative, up-to-date
phase-by-phase status.
