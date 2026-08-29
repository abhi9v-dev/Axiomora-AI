import { act, renderHook, waitFor } from "@testing-library/react";
import type { RunSnapshot } from "@bi-copilot/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRun } from "@/lib/useRun";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  listeners: Record<string, ((event: { data: string }) => void)[]> = {};
  closed = false;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: { data: string }) => void) {
    (this.listeners[type] ??= []).push(handler);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data: unknown) {
    this.listeners[type]?.forEach((handler) => handler({ data: JSON.stringify(data) }));
  }
}

function snapshot(overrides: Partial<RunSnapshot> = {}): RunSnapshot {
  return {
    run_id: "abc",
    tenant_id: "default",
    source_id: "marketplace_demo",
    question: "Why did hold time spike?",
    status: "RECEIVED",
    retrieved_context: [],
    attempts: [],
    insight: null,
    insight_error: null,
    clarification_question: null,
    clarification_options: null,
    clarification_answer: null,
    error: null,
    created_at: "2026-08-29T00:00:00Z",
    updated_at: "2026-08-29T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

describe("useRun", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("start() posts a run and opens an SSE connection for it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: "abc", status: "RECEIVED" }), { status: 202 }),
    );

    const { result } = renderHook(() => useRun());
    await act(async () => {
      await result.current.start("Why did hold time spike?");
    });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/runs"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.url).toContain("/api/v1/runs/abc/events");
  });

  it("applies snapshots received over the SSE connection", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: "abc", status: "RECEIVED" }), { status: 202 }),
    );

    const { result } = renderHook(() => useRun());
    await act(async () => {
      await result.current.start("q");
    });
    act(() => {
      FakeEventSource.instances[0]?.emit("run_update", snapshot({ status: "READY" }));
    });

    await waitFor(() => expect(result.current.snapshot?.status).toBe("READY"));
  });

  it("surfaces a failed start() as an error message, not a thrown exception", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "question must not be empty" }), { status: 422 }),
    );

    const { result } = renderHook(() => useRun());
    await act(async () => {
      await result.current.start("");
    });

    await waitFor(() => expect(result.current.error).toBe("question must not be empty"));
    expect(result.current.snapshot).toBeNull();
  });

  it("given an initialRunId, loads the existing run and subscribes to it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(snapshot({ status: "READY" })), { status: 200 }),
    );

    const { result } = renderHook(() => useRun("abc"));

    await waitFor(() => expect(result.current.snapshot?.run_id).toBe("abc"));
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.url).toContain("/api/v1/runs/abc/events");
  });

  it("answerClarification posts the answer and re-subscribes over a fresh connection", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: "abc", status: "RECEIVED" }), { status: 202 }),
    );
    const { result } = renderHook(() => useRun());
    await act(async () => {
      await result.current.start("q");
    });
    act(() => {
      FakeEventSource.instances[0]?.emit(
        "run_update",
        snapshot({ status: "NEEDS_CLARIFICATION", clarification_question: "Which department?" }),
      );
    });
    await waitFor(() => expect(result.current.snapshot?.status).toBe("NEEDS_CLARIFICATION"));

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: "abc", status: "RECEIVED" }), { status: 202 }),
    );
    await act(async () => {
      await result.current.answerClarification("Buyer department");
    });

    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringContaining("/clarification"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(FakeEventSource.instances[0]?.closed).toBe(true);
  });

  it("cancel() posts to the cancel endpoint and applies the returned snapshot", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: "abc", status: "RECEIVED" }), { status: 202 }),
    );
    const { result } = renderHook(() => useRun());
    await act(async () => {
      await result.current.start("q");
    });
    act(() => {
      FakeEventSource.instances[0]?.emit("run_update", snapshot({ status: "GENERATING_SQL" }));
    });
    await waitFor(() => expect(result.current.snapshot?.status).toBe("GENERATING_SQL"));

    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(snapshot({ status: "CANCELLED" })), { status: 200 }),
    );
    await act(async () => {
      await result.current.cancel();
    });

    expect(result.current.snapshot?.status).toBe("CANCELLED");
  });
});
