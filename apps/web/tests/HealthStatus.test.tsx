import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HealthStatus } from "@/components/HealthStatus";

describe("HealthStatus", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows OK for both checks when the API responds successfully", async () => {
    vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/health")) {
        return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
      }
      return new Response(JSON.stringify({ status: "ready", checks: { database: "ok" } }), {
        status: 200,
      });
    });

    render(<HealthStatus />);

    expect(screen.getAllByText("Checking…").length).toBeGreaterThan(0);

    await waitFor(() => {
      expect(screen.getAllByText("OK")).toHaveLength(2);
    });
  });

  it("shows Unreachable when the API cannot be reached", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("network error"));

    render(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getAllByText("Unreachable")).toHaveLength(2);
    });
    expect(screen.getAllByText("Could not reach the API.").length).toBeGreaterThan(0);
  });

  it("shows Degraded when the readiness check fails", async () => {
    vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
      const url = input.toString();
      if (url.endsWith("/health")) {
        return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
      }
      return new Response(
        JSON.stringify({ status: "not_ready", checks: { database: "error: timeout" } }),
        { status: 503 },
      );
    });

    render(<HealthStatus />);

    await waitFor(() => {
      expect(screen.getByText("OK")).toBeInTheDocument();
      expect(screen.getByText("Degraded")).toBeInTheDocument();
    });
    expect(screen.getByText("database: error: timeout")).toBeInTheDocument();
  });
});
