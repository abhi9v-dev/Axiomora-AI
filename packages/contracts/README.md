# packages/contracts

Reserved for request/response contracts that need to be shared between the
Python backend and the TypeScript frontend (see
[docs/06_DATA_MODEL_API_CONTRACTS.md](../../docs/06_DATA_MODEL_API_CONTRACTS.md)).

Each agent's own versioned Pydantic contract lives beside that agent
instead (e.g. `apps/api/app/nl2sql/schema.py` for the NL2SQL Agent,
introduced in Phase 3) until it genuinely needs to be consumed outside the
API process too. That's expected starting around Phase 6, when the
frontend needs typed shapes for run/answer responses. Nothing here is used
yet.
