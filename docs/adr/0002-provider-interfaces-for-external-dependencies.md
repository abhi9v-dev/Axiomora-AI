# ADR 0002: Provider interfaces for the LLM, embeddings and external actions

## Status

Accepted (established in the Phase 0 foundation).

## Context

The project must be developable and testable without incurring Claude API
cost on every test run, and without ever letting the language model hold
credentials or open a direct connection to the database or to Power BI (see
`CLAUDE.md` architecture invariants). It must also remain possible to run
the full test suite deterministically in CI.

## Decision

Every external dependency that is expensive, non-deterministic, or
security-sensitive is accessed through a small typed interface, with at
least two implementations:

- `LLMProvider`: a `FakeLLMProvider` (deterministic, no network calls) and
  an `AnthropicLLMProvider` (Phase 3+). `LLM_PROVIDER=fake` is the default in
  `.env.example` so a fresh checkout runs with zero external calls.
- `EmbeddingProvider`: same pattern, `EMBEDDING_PROVIDER=fake` by default
  (Phase 2+).
- Action destinations (Excel export, Power BI): the Power BI adapter is
  built against a mock server first (Phase 8), with real integration behind
  `POWER_BI_ENABLED=false` by default.

The orchestrator and API layer depend only on these interfaces, never on a
concrete provider class. Credentials for real providers are read from typed
`Settings` (`apps/api/app/config.py`) and are never passed into a prompt or
exposed to the LLM.

## Consequences

- Unit and integration tests run deterministically and without cost using
  the fake providers.
- Swapping or upgrading a real provider (e.g. a new Claude model) touches
  one adapter, not the orchestrator or agents.
- A compromised or hallucinating LLM response cannot reach a database
  connection or an external API directly — it can only return data that the
  orchestrator's typed contracts and policy checks then evaluate.
- Contributors must remember to keep new external dependencies behind the
  same pattern rather than importing an SDK directly into agent logic.
