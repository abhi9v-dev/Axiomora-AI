import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { RunSnapshot } from "@bi-copilot/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunView } from "@/components/RunView";

function readySnapshot(overrides: Partial<RunSnapshot> = {}): RunSnapshot {
  return {
    run_id: "abc",
    tenant_id: "default",
    source_id: "marketplace_demo",
    question: "Why did hold time spike?",
    status: "READY",
    retrieved_context: [],
    attempts: [
      {
        attempt_no: 1,
        nl2sql: {
          sql: "SELECT 1",
          dialect: "postgres",
          referenced_objects: [],
          assumptions: [],
          parameters: {},
          confidence: 0.9,
        },
        validator: {
          status: "pass",
          checks: [{ name: "sql_policy", status: "pass", details: "ok" }],
          repairable: false,
          feedback: null,
          result: { columns: ["x"], rows: [[1]], row_count: 1, truncated: false },
        },
      },
    ],
    insight: { headline: "h", narrative: "n", claims: [], chart: null },
    insight_error: null,
    clarification_question: null,
    clarification_options: null,
    clarification_answer: null,
    error: null,
    created_at: "2026-08-30T00:00:00Z",
    updated_at: "2026-08-30T00:00:00Z",
    completed_at: "2026-08-30T00:00:00Z",
    ...overrides,
  };
}

describe("RunView export action", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    // jsdom doesn't implement these at all (not even a throwing stub), so
    // there's nothing for vi.spyOn to wrap -- assign fakes directly.
    // Clicking the real <a download> anchor still logs a harmless jsdom
    // "Not implemented: navigation" stderr line (it doesn't actually
    // support blob: navigation) -- expected noise, not a test failure.
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("confirms and downloads the workbook via a fresh idempotency key", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(new Blob(["fake-xlsx"]), {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="run.xlsx"' },
      }),
    );

    render(
      <RunView snapshot={readySnapshot()} onAnswerClarification={vi.fn()} onCancel={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Export Excel" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/runs/abc/actions");
    const body = JSON.parse(init.body as string) as { type: string; idempotency_key: string };
    expect(body.type).toBe("export_excel");
    expect(typeof body.idempotency_key).toBe("string");
    expect(body.idempotency_key.length).toBeGreaterThan(0);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows an error in the dialog when export fails", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "not ready" }), { status: 403 }),
    );

    render(
      <RunView snapshot={readySnapshot()} onAnswerClarification={vi.fn()} onCancel={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Export Excel" }));
    await user.click(screen.getByRole("button", { name: "Download" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("not ready"));
    // The dialog must stay open on failure so the user can retry or cancel.
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("does not show the export button before a validated result exists", () => {
    const snapshot = readySnapshot({ status: "GENERATING_SQL", attempts: [] });

    render(<RunView snapshot={snapshot} onAnswerClarification={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Export Excel" })).not.toBeInTheDocument();
  });

  it("cancelling the dialog closes it without calling fetch", async () => {
    const user = userEvent.setup();
    render(
      <RunView snapshot={readySnapshot()} onAnswerClarification={vi.fn()} onCancel={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Export Excel" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
