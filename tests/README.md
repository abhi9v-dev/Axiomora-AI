# tests

Reserved for cross-cutting integration and end-to-end suites that span both
`apps/api` and `apps/web` (for example, Playwright flows driving the real
frontend against the real backend).

App-local unit/contract tests live beside their app instead: `apps/api/tests`
(pytest) and `apps/web/tests` (Vitest). This directory is populated starting
Phase 4 (integration tests against a live read-only warehouse) and Phase 6
(Playwright end-to-end tests).
