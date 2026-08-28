# Deployment & Operations Runbook

## Local zero-cost setup

Run PostgreSQL/pgvector via Docker Compose, and the API/web apps as local dev
servers. Seed synthetic data (Phase 1+). Configure `LLM_PROVIDER=fake` for
deterministic development, then add an Anthropic key for live model runs.
See the root [README.md](../README.md) for exact commands.

## Hosted demo topology

- Static/Next.js frontend on a free web tier.
- FastAPI on a free container/Python tier that may sleep when idle.
- Managed PostgreSQL/pgvector on a free tier, or self-host for
  demonstrations.
- Excel files generated on demand and downloaded immediately.
- No production PII and no permanent warehouse credential in preview
  deployments.

Provider names and quotas should be chosen at deployment time because free
plans change. Verify current limits before committing to one. This topology
is realized in Phase 9.

## Power BI reality check

Power BI REST operations require Microsoft Entra registration, tenant
permissions and appropriate Power BI/Fabric licensing/capacity for the
chosen operation. Therefore:

- Implement an adapter and a mock server first.
- Keep `POWER_BI_ENABLED=false` by default.
- Demonstrate the action workflow with Excel at no additional software cost.
- Enable real Power BI only when the tenant administrator and license
  support it.

## Deployment checklist

1. Run lint, type checks, unit, integration and E2E tests.
2. Apply database migrations and seed catalog/demo warehouse.
3. Create read-only warehouse credentials.
4. Configure secrets in the platform, never in source control.
5. Enable HTTPS, allowed origins and secure cookies.
6. Run smoke questions and verify audit events.
7. Confirm SQL policy with adversarial inputs.
8. Test Excel download and idempotency.
9. Add budget/rate limits for live LLM usage.

## Observability

Expose health/readiness endpoints (Phase 0: `GET /health`, `GET /ready`),
structured logs keyed by `run_id`, step durations, model token usage, SQL
duration, validation failures and action outcomes. Never log secrets or raw
sensitive values.

## Recovery

Application migrations must be reversible when possible. Failed actions can
be retried using the same idempotency key. If the model service is
unavailable, preserve the run as retryable. Disable actions independently
through feature flags.
