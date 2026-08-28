# Data Model, API & Agent Contracts

## Core application entities

| Entity            | Important fields                                                              |
| ------------------- | --------------------------------------------------------------------------------- |
| `data_source`         | id, tenant_id, name, dialect, allowed_schemas, status                              |
| `catalog_document`    | id, source_id, kind, object_name, content, version, embedding                       |
| `run`                 | id, user_id, source_id, question, status, started_at, completed_at                  |
| `sql_attempt`         | id, run_id, attempt_no, sql_text, ast_hash, policy_result                           |
| `query_result`        | id, run_id, columns_json, rows_json/file_ref, fingerprint                            |
| `validation`          | id, run_id, check_type, status, details_json                                        |
| `insight`             | id, run_id, narrative, claims_json, model_version                                    |
| `action`              | id, run_id, type, destination, status, idempotency_key, approved_by                 |
| `audit_event`         | id, tenant_id, actor, event_type, target_id, payload_hash, timestamp                |

These are introduced starting with Phase 1 (warehouse/star-schema entities)
and Phase 2+ (application entities above, via Alembic migrations under
`/migrations`). Phase 0 defines no application tables.

## Public API

| Method | Path                                     | Purpose                        |
| ------ | ------------------------------------------ | --------------------------------- |
| POST   | `/api/v1/runs`                              | Start a question run              |
| GET    | `/api/v1/runs/{run_id}`                     | Get full safe run state           |
| GET    | `/api/v1/runs/{run_id}/events`              | SSE progress stream                |
| POST   | `/api/v1/runs/{run_id}/clarification`       | Submit clarification               |
| POST   | `/api/v1/runs/{run_id}/cancel`              | Cancel a run                       |
| POST   | `/api/v1/runs/{run_id}/actions`             | Request export/publish             |
| GET    | `/api/v1/catalog/search`                    | Search governed catalog            |
| POST   | `/api/v1/catalog/ingest`                    | Admin-only catalog ingestion       |

Phase 0 ships only `GET /health` and `GET /ready`. The table above is the
target surface built incrementally from Phase 2 (catalog) through Phase 7
(actions).

## Start-run request

```json
{
  "source_id": "retail_demo",
  "question": "Why did margin drop in Q2 for the West region?",
  "timezone": "UTC"
}
```

## NL2SQL output

```json
{
  "sql": "SELECT ...",
  "dialect": "postgres",
  "referenced_objects": ["analytics.fact_sales", "analytics.dim_store"],
  "assumptions": ["Q2 refers to the latest complete fiscal Q2"],
  "parameters": { "region_code": "W" },
  "confidence": 0.86
}
```

## Validator output

```json
{
  "status": "pass",
  "checks": [{ "name": "margin_range", "status": "pass", "details": "0..1" }],
  "repairable": false,
  "feedback": null
}
```

## Insight output

```json
{
  "headline": "West margin decreased 7 percentage points",
  "narrative": "The decrease was primarily associated with higher apparel COGS.",
  "claims": [
    {
      "text": "Margin moved from 34% to 27%",
      "evidence": ["result:r2:c4", "result:r3:c4"]
    }
  ],
  "chart": { "type": "bar", "x": "category", "y": "margin_change_pp" }
}
```

All agent responses must be parsed against versioned JSON schemas (Pydantic
models in `packages/contracts` once introduced). Invalid responses are
retried once for formatting; they are never trusted as free-form control
instructions.
