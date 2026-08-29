# packages/contracts

Request/response contracts shared between the Python backend and the
TypeScript frontend (see
[docs/06_DATA_MODEL_API_CONTRACTS.md](../../docs/06_DATA_MODEL_API_CONTRACTS.md)).

Each agent's own versioned Pydantic contract still lives beside that agent
(e.g. `apps/api/app/nl2sql/schema.py`) -- that stays the source of truth.
`src/run.ts` is a hand-maintained TypeScript mirror of the shapes the
frontend actually consumes over HTTP (`RunSnapshot` and everything nested
in it), introduced in Phase 6 when `apps/web`'s `/ask` page first needed
typed run/answer responses. There is no schema-generation step in this
project, so when a Python contract changes, update its mirror here in the
same change.

A pnpm workspace package (`@bi-copilot/contracts`, see the repo-root
`pnpm-workspace.yaml`) consumed directly as TypeScript source -- no build
step -- via Next.js's `transpilePackages` (`apps/web/next.config.ts`).
