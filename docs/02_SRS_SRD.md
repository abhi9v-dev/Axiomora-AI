# Software Requirements Specification / System Requirements Document

## Functional requirements

| ID     | Requirement                                                              | Priority |
| ------ | ------------------------------------------------------------------------- | -------- |
| FR-001 | Ingest table, column, relationship, glossary and measure documentation    | Must     |
| FR-002 | Chunk, embed and version schema knowledge                                 | Must     |
| FR-003 | Retrieve relevant context for each question with source identifiers       | Must     |
| FR-004 | Generate SQL only from approved context and dialect                       | Must     |
| FR-005 | Parse and reject non-SELECT SQL, unapproved objects and risky constructs  | Must     |
| FR-006 | Execute with read-only credentials, timeout and row cap                   | Must     |
| FR-007 | Validate schema use, result shape, ranges, reconciliation and anomalies   | Must     |
| FR-008 | Retry SQL at most twice using structured validator feedback               | Must     |
| FR-009 | Generate a narrative using only validated result data                     | Must     |
| FR-010 | Display evidence, SQL, assumptions and validation outcome                 | Must     |
| FR-011 | Export results, narrative and metadata to `.xlsx`                        | Must     |
| FR-012 | Keep immutable audit events for agent and action steps                    | Should   |
| FR-013 | Publish or refresh Power BI through a feature-flagged adapter             | Should   |
| FR-014 | Ask for clarification when ambiguity materially changes SQL               | Should   |
| FR-015 | Allow analysts to rate/correct an answer                                  | Should   |

## Agent responsibilities

| Agent    | Input                                    | Output                                          | Forbidden behavior                                       |
| -------- | ----------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------- |
| Schema   | Question, tenant, source                  | Ranked governed context, citations               | Inventing schema definitions                                |
| NL2SQL   | Question, context, dialect                | SQL plus assumptions, parameters, confidence     | Executing SQL or using unknown/unapproved objects            |
| Validator| SQL, policy, execution result             | Pass/fail, checks, repair feedback               | Editing data or silently accepting failures                  |
| Insight  | Validated dataset                         | Claims, narrative, chart suggestion              | Introducing unsupported numbers                              |
| Action   | Approved action request                   | Export/publish receipt                           | Acting without policy and approval checks                    |

## Non-functional requirements

- **Security**: least privilege, tenant isolation, secret management, TLS in
  hosted environments.
- **Reliability**: idempotent action requests, bounded retries, useful
  failure states.
- **Performance**: P95 ≤ 20 seconds on demo queries; retrieval P95 ≤ 2
  seconds.
- **Explainability**: display selected sources, final SQL, validation checks
  and data timestamp.
- **Maintainability**: typed contracts, modular adapters, migrations and
  automated tests.
- **Accessibility**: keyboard navigation, visible focus, semantic labels and
  WCAG AA color contrast.
- **Privacy**: redact secrets and configured sensitive fields from prompts
  and logs.
- **Portability**: local Docker Compose and cloud services replaceable
  through interfaces.

## Constraints and assumptions

- MVP supports PostgreSQL first.
- Source access uses a dedicated read-only role.
- The demo uses synthetic retail data and contains no personal information.
- Claude API use is not inherently free; development may use credits or a
  local mock provider. Hosting can be free-tier, but model and Power BI costs
  depend on account/licensing.
- "Real time" means synchronous questions over current warehouse data plus
  visible streaming progress; it does not imply continuous streaming
  ingestion in MVP.

## Traceability

Every accepted user story must map to requirement IDs, tests and a release
phase. No phase closes until its Must requirements pass automated or
documented manual acceptance tests.

Phase 0 does not implement any FR-### item directly (those begin at Phase
1/2); it establishes the foundation (repo, services, config, health checks)
that every later requirement depends on.
