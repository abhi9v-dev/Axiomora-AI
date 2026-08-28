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
  "source_id": "marketplace_demo",
  "question": "Why did median task hold time spike for the Buyer department in Q2?",
  "timezone": "UTC"
}
```

## NL2SQL output

```json
{
  "sql": "SELECT ...",
  "dialect": "postgres",
  "referenced_objects": ["analytics.v_task_lifecycle", "organisation.department"],
  "assumptions": ["Q2 refers to the latest complete fiscal Q2"],
  "parameters": { "department_name": "Buyer" },
  "confidence": 0.86
}
```

## Validator output

```json
{
  "status": "pass",
  "checks": [{ "name": "hold_hours_non_negative", "status": "pass", "details": ">= 0" }],
  "repairable": false,
  "feedback": null
}
```

## Insight output

```json
{
  "headline": "Buyer department median hold time increased 18 hours in Q2",
  "narrative": "The increase was primarily associated with Supplier Compliance Review tasks taking far longer to be claimed and completed.",
  "claims": [
    {
      "text": "Median hold time moved from 9.5 hours to 27.4 hours",
      "evidence": ["result:r2:c4", "result:r3:c4"]
    }
  ],
  "chart": { "type": "bar", "x": "task_subtype", "y": "hold_time_change_hrs" }
}
```

All agent responses must be parsed against versioned JSON schemas (Pydantic
models in `packages/contracts` once introduced). Invalid responses are
retried once for formatting; they are never trusted as free-form control
instructions.
