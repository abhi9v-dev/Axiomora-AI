# ADR 0003: Marketplace-operations demo domain (replaces retail)

## Status

Accepted (2026-08-28, before Phase 1 implementation began).

## Context

The original build specification's demo domain was retail sales: a
`fact_sales` / `dim_date` / `dim_store` / `dim_product` star schema with a
known Q2 West-region margin decline driven by apparel COGS, used throughout
`docs/` as the running example.

During Phase 0 wrap-up, the user provided a real-world schema and query set
(`marketplace.projects`, `marketplace.task`, `organisation.department`,
`organisation.account`, plus `analytics.v_task_lifecycle` /
`analytics.v_project_status` rollup views) from a procurement/marketplace
workflow platform, and asked to use it as the project's example domain
instead of retail. The user confirmed the underlying data is synthetic/
sanitized and explicitly chose to replace the retail domain entirely rather
than run it alongside.

## Decision

The demo domain is now **marketplace operations**: projects flow through
stages/statuses, and tasks within a project are claimed, started and
completed (or abandoned) by department members. Core analytics are task
lifecycle timing (claim wait, start delay, hold time) and project health
(stuck/unclaimed detection), rather than sales/margin analysis.

All seed data remains synthetic — fabricated rows generated to match the
*shape* of the provided schema and views, not real records — so the
project's existing rule (`CLAUDE.md`: "synthetic data only, no personal
information") holds even though the schema itself is modeled on a real
system.

The Phase 1 seed anomaly (replacing "Q2 West margin drop driven by apparel
COGS") is: **median task hold time in the Buyer department spikes in Q2,
driven by Supplier Compliance Review tasks** taking far longer than other
task subtypes to be claimed and completed. This plays the same structural
role — an aggregate KPI change in one dimension, with one identifiable top
driver — so it exercises the same NL2SQL/Validator/Insight capabilities the
original story was designed to prove out.

`docs/01_PRD.md` through `docs/10_IMPLEMENTATION_ROADMAP.md`, `CLAUDE.md`
and `README.md` were updated to reference this domain instead of retail.

## Consequences

- The five-agent pipeline itself required no change: it was already
  designed to be domain-agnostic (ADR 0001, ADR 0002) via the `data_source`
  abstraction, catalog-driven schema retrieval, and per-source validator
  allowlists. This swap only touches demo content — seed data, glossary
  terms, benchmark questions, doc examples — not the architecture.
- Phase 1 now builds `marketplace.*` / `organisation.*` tables and the two
  analytics views instead of a star schema; Phase 2's glossary/measure
  documents describe this schema instead of retail measures like margin or
  COGS.
- Any future contributor reading an older discussion or draft that
  references `fact_sales`, "West region", or "apparel COGS" should treat it
  as superseded by this ADR.
