# Test, Evaluation & Acceptance Plan

## Test pyramid

1. **Unit**: parsers, allowlists, calculations, validators and formatters.
2. **Contract**: JSON schemas for all agents and API responses.
3. **Integration**: pgvector retrieval, read-only query execution, retries
   and exports.
4. **End-to-end**: browser question-to-answer and action flows.
5. **Evaluation**: benchmark questions scored for SQL and answer
   correctness.
6. **Security**: injection, authorization and action abuse tests.

Phase 0 exercises layers 1 and 3 only (config/health unit tests, and a
manual/local integration check that Postgres+pgvector starts via Compose).

## Golden benchmark dataset

Seed a synthetic marketplace-operations schema (`marketplace.projects`,
`marketplace.task`, `organisation.department`, `organisation.account`, and
the `analytics.v_task_lifecycle` / `analytics.v_project_status` rollup
views) with controlled anomalies. Maintain at least 20 questions across
aggregation, time comparison, filtering, ranking, contribution analysis and
ambiguity. Introduced in Phase 1.

## Example acceptance cases

| ID    | Case                             | Expected                                            |
| ----- | ----------------------------------- | ------------------------------------------------------ |
| AT-01 | Hold-time spike, Buyer dept, Q2       | Correct comparison and top drivers                       |
| AT-02 | Ambiguous "last quarter"              | Clarify fiscal/calendar if not configured                 |
| AT-03 | Prompt asks to DELETE                 | Block before execution                                     |
| AT-04 | Join duplicates task counts            | Validation fails or SQL is repaired                        |
| AT-05 | Result is empty                        | Explain no data; do not invent insight                      |
| AT-06 | Narrative adds unsupported number       | Evidence binding rejects response                            |
| AT-07 | Repeat export request                   | One workbook per idempotency key                              |
| AT-08 | Unauthorized Power BI action             | 403 and audit event                                            |

## Evaluation metrics

- Retrieval recall@5 for required schema objects.
- SQL execution accuracy.
- Result equivalence against golden SQL.
- Validator true-positive/false-positive rate.
- Claim grounding precision.
- End-to-end latency and token usage.

## Release gates

- No critical/high security finding.
- All Must requirements have tests.
- Zero unsafe execution in the adversarial suite.
- 100% of numerical claims contain valid evidence pointers.
- Backup/restore and rollback instructions tested for the deployed demo.

## Phase 0 acceptance criteria

Phase 0 is complete when:

- The repository structure exists.
- PostgreSQL with pgvector can run through Docker Compose.
- The FastAPI service starts successfully.
- `/health` returns a successful response.
- `/ready` verifies application/database readiness.
- The Next.js frontend starts and displays the project shell.
- The frontend can call and display backend health status.
- Typed configuration is implemented and validates required variables at
  startup.
- `.env.example` contains placeholders only.
- Backend tests pass.
- Frontend tests pass.
- Linting and type-checking pass for both apps.
- Setup and run instructions are documented (`README.md`).
