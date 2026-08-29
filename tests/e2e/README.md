# tests/e2e

Playwright end-to-end suite driving the real Next.js frontend against the
real FastAPI backend (docs/10_IMPLEMENTATION_ROADMAP.md's Phase 6 exit
criterion: "Playwright completes the full question flow"). Runs in CI as
the `e2e` job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml),
against a real `pgvector/pgvector:pg16` service, migrated/seeded/ingested
the same way local dev is.

`ask-flow.spec.ts` asks the one question the synthetic warehouse was
deliberately seeded to answer (`app.db.seed`'s hold-time anomaly) and that
`LLM_PROVIDER=fake` has a real scripted response for
(`apps/api/app/llm/demo.py`) -- so the happy path exercises the actual
orchestrator, warehouse and claim-verification logic, at zero API cost.
It also checks that an unscripted question fails visibly rather than
silently, and that a run's own `/runs/[id]` page reproduces the same
answer from history.

## Running locally

```bash
# From the repo root, with the db service up and migrated/seeded/ingested
# (see the top-level README.md's "First-time setup"):
cd apps/api && uvicorn app.main:app --port 8000 &
cd apps/web && pnpm run build && pnpm run start -- --port 3000 &

cd tests/e2e
pnpm exec playwright install --with-deps chromium   # once
pnpm run test
```

`E2E_BASE_URL` overrides the web app's base URL (default
`http://localhost:3000`); the web app itself must have been built/started
with `NEXT_PUBLIC_API_BASE_URL` pointing at the running API.
