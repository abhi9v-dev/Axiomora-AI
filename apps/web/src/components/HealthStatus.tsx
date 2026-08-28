"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/env";

type CheckState = "loading" | "ok" | "degraded" | "unreachable";

interface FetchedStatus {
  state: CheckState;
  detail?: string;
}

async function fetchStatus(baseUrl: string, path: string): Promise<FetchedStatus> {
  try {
    const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
    const body = (await response.json().catch(() => undefined)) as
      { checks?: Record<string, string> } | undefined;
    const detail = body?.checks
      ? Object.entries(body.checks)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ")
      : undefined;
    return { state: response.ok ? "ok" : "degraded", detail };
  } catch {
    return { state: "unreachable", detail: "Could not reach the API." };
  }
}

const STATUS_PRESENTATION: Record<CheckState, { icon: string; label: string; className: string }> =
  {
    loading: { icon: "○", label: "Checking…", className: "text-neutral-500" },
    ok: { icon: "✓", label: "OK", className: "text-verified" },
    degraded: { icon: "⚠", label: "Degraded", className: "text-warning" },
    unreachable: { icon: "✕", label: "Unreachable", className: "text-blocked" },
  };

function StatusRow({ label, status }: { label: string; status: FetchedStatus }) {
  const presentation = STATUS_PRESENTATION[status.state];
  return (
    <div className="flex items-start justify-between gap-4 border-b border-neutral-200 py-3 last:border-0">
      <span className="font-medium text-neutral-700">{label}</span>
      <span className="text-right">
        <span className={`font-semibold ${presentation.className}`}>
          <span aria-hidden="true">{presentation.icon}</span> {presentation.label}
        </span>
        {status.detail ? (
          <span className="block text-xs text-neutral-500">{status.detail}</span>
        ) : null}
      </span>
    </div>
  );
}

export function HealthStatus() {
  const baseUrl = getApiBaseUrl();
  const [health, setHealth] = useState<FetchedStatus>({ state: "loading" });
  const [ready, setReady] = useState<FetchedStatus>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchStatus(baseUrl, "/health").then((result) => {
      if (!cancelled) setHealth(result);
    });
    fetchStatus(baseUrl, "/ready").then((result) => {
      if (!cancelled) setReady(result);
    });

    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  return (
    <section
      aria-label="Backend status"
      className="w-full max-w-md rounded-lg border border-neutral-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Backend status
      </h2>
      <div>
        <StatusRow label="API health" status={health} />
        <StatusRow label="API readiness" status={ready} />
      </div>
      <p className="mt-3 text-xs text-neutral-400">Backend: {baseUrl}</p>
    </section>
  );
}
