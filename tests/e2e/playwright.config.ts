import { defineConfig, devices } from "@playwright/test";

/**
 * Drives the real Next.js frontend against the real FastAPI backend
 * (docs/10_IMPLEMENTATION_ROADMAP.md Phase 6 exit criterion: "Playwright
 * completes the full question flow"). Both servers, the database
 * migration/seed/catalog-ingest steps, and LLM_PROVIDER=fake's demo script
 * (app.llm.demo) are started/prepared by the CI workflow (or manually
 * locally) before this runs -- see .github/workflows/ci.yml's `e2e` job
 * and README.md's "First-time setup".
 */
export default defineConfig({
  testDir: "./specs",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
