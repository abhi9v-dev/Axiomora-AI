# Frontend Product & UX Specification

## Information architecture

| Route          | Purpose                                             |
| --------------- | ----------------------------------------------------- |
| `/ask`          | Ask questions and inspect answers                     |
| `/runs/[id]`    | Reproducible run details                               |
| `/catalog`      | Browse schema, glossary and indexing state             |
| `/actions`      | Action history and approvals                           |
| `/settings`     | Connections, model and policy configuration             |

Phase 0 ships only the root `/` shell (project identity + backend health).
The routes above are introduced starting with Phase 6.

## Ask page

- Source selector, question composer, sample questions and history.
- Streaming stepper: Understanding → Finding schema → Writing SQL →
  Validating → Explaining.
- Answer header with validation badge, data timestamp and elapsed time.
- KPI cards and result table; chart only when the response contains a valid
  chart specification.
- Narrative section with numbered claims. Clicking a claim highlights
  supporting cells.
- Collapsible "Evidence & SQL" panel containing retrieved definitions,
  assumptions, SQL and checks.
- Actions: Export Excel; Publish to Power BI when enabled and authorized.

## Critical states

| State              | UX behavior                                                          |
| -------------------- | ------------------------------------------------------------------------ |
| Empty                 | Example questions based on selected source                              |
| Running               | Streaming progress and cancel option; no fake percentages                |
| Clarification          | One focused question with selectable interpretations                     |
| Validation failed      | No narrative; show safe diagnostic and analyst details                    |
| Success                | Results, grounded narrative, evidence and available actions               |
| Action pending         | Explicit destination and impact confirmation                             |
| Error                  | Stable run ID, retry and non-sensitive error message                     |

## Visual direction

Professional analytics workspace: neutral background, indigo primary
accent, green only for verified status, amber for warnings and red for
blocked actions. Dense tables remain readable; code uses a monospaced font.
Desktop-first, responsive down to tablet.

Phase 0's Tailwind theme (`apps/web/tailwind.config.ts`) already encodes this
palette (`accent`, `verified`, `warning`, `blocked`) so later phases reuse it
consistently rather than re-deriving colors per component.

## Components

`QuestionComposer`, `AgentProgress`, `ClarificationCard`, `ValidationBadge`,
`KpiGrid`, `ResultDataGrid`, `InsightNarrative`, `EvidenceDrawer`,
`SqlViewer`, `ActionDialog`, `RunHistory`.

These are introduced incrementally starting with Phase 6.

## Accessibility and behavior

- All actions keyboard accessible and labeled.
- Status is communicated by text/icon, not color alone.
- Tables include headers and downloadable alternatives.
- Preserve question drafts and route state.
- Never render raw model HTML.
- Use server-sent events for progress; reconnect by `run_id`.
