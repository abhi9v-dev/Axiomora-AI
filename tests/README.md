# tests

Reserved for cross-cutting integration and end-to-end suites that span both
`apps/api` and `apps/web` (for example, Playwright flows driving the real
frontend against the real backend).

App-local tests -- including backend-only integration tests against a live
database (e.g. the read-only warehouse, the semantic catalog, the
Validator Agent) -- live beside their app instead: `apps/api/tests`
(pytest) and `apps/web/tests` (Vitest). Those only need one app running,
so splitting them into a separately-configured root suite would add
friction for no benefit. This directory is reserved for suites that
genuinely need both apps at once, starting with Phase 6's Playwright
end-to-end tests.
