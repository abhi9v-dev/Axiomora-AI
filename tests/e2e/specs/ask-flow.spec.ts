import { expect, test } from "@playwright/test";

/**
 * Must match app.llm.demo.build_demo_llm_provider's scripted question
 * (LLM_PROVIDER=fake) and apps/web/src/components/QuestionComposer.tsx's
 * first sample question -- kept in sync by hand, same as the rest of this
 * project's cross-language contracts (no shared-constant mechanism between
 * Python and this Playwright suite).
 */
const DEMO_QUESTION = "Why did median task hold time spike for the Buyer department in Q2?";

test.describe("Ask flow", () => {
  test("asking the seeded demo question produces a validated, evidence-grounded answer", async ({
    page,
  }) => {
    await page.goto("/ask");

    await page.getByRole("button", { name: DEMO_QUESTION }).click();
    await page.getByRole("button", { name: "Ask", exact: true }).click();

    await expect(page.getByLabel("Answer progress")).toBeVisible();

    // Real retrieval + NL2SQL + validation + insight generation against a
    // live warehouse -- generous timeout for CI, not a fixed sleep.
    await expect(page.getByText("Validated", { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /buyer department/i })).toBeVisible();

    await page.getByText("Evidence & SQL").click();
    await expect(page.getByText(/analytics\.v_task_lifecycle/)).toBeVisible();

    await expect(page.locator("aside").getByText(DEMO_QUESTION)).toBeVisible();
  });

  test("an unscripted question surfaces a clear failure state, not a crash", async ({ page }) => {
    await page.goto("/ask");

    await page.getByLabel("Ask a business question").fill("What is the meaning of life?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();

    await expect(page.getByText(/could not produce a validated answer/i)).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/Run ID:/)).toBeVisible();
  });

  test("exports a validated answer as a downloadable workbook", async ({ page }) => {
    await page.goto("/ask");
    await page.getByRole("button", { name: DEMO_QUESTION }).click();
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("Validated", { exact: true })).toBeVisible({ timeout: 30_000 });

    // Byte-level content and same-idempotency-key deduplication are
    // covered in apps/api/tests/test_workbook.py and
    // test_action_store_integration.py; this checks the click-through UX
    // actually produces a real download end to end (AT-07's "approved run
    // downloads a correct workbook").
    await page.getByRole("button", { name: "Export Excel" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByText("Download to your device")).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download" }).click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/^bi-copilot-run-.*\.xlsx$/);
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });

  test("a run's own page reproduces the same answer from history", async ({ page }) => {
    await page.goto("/ask");
    await page.getByRole("button", { name: DEMO_QUESTION }).click();
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByText("Validated", { exact: true })).toBeVisible({ timeout: 30_000 });

    await page.locator("aside").getByText(DEMO_QUESTION).click();

    await expect(page).toHaveURL(/\/runs\/[0-9a-fA-F-]+$/);
    await expect(page.getByText("Validated", { exact: true })).toBeVisible();
  });
});
