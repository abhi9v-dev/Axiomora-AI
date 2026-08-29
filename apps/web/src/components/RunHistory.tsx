"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { RunSummary } from "@bi-copilot/contracts";
import { listRuns } from "@/lib/api";
import { getApiBaseUrl } from "@/lib/env";

/** docs/05_FRONTEND_UX.md's Ask page: "...and history." `refreshKey`
 * changing (e.g. after a new run is started) triggers a re-fetch, since
 * the history list has no other way to learn about a run this session
 * itself just created. */
export function RunHistory({ refreshKey }: { refreshKey?: number }) {
  const baseUrl = getApiBaseUrl();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listRuns(baseUrl, 20)
      .then((items) => {
        if (!cancelled) setRuns(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load history.");
      });
    return () => {
      cancelled = true;
    };
  }, [baseUrl, refreshKey]);

  if (error) return <p className="text-xs text-blocked">Could not load run history.</p>;
  if (!runs) return <p className="text-xs text-neutral-400">Loading history…</p>;
  if (runs.length === 0) return <p className="text-xs text-neutral-400">No questions asked yet.</p>;

  return (
    <ul className="space-y-2">
      {runs.map((run) => (
        <li key={run.run_id}>
          <Link
            href={`/runs/${run.run_id}`}
            className="block rounded-md border border-neutral-200 p-2 text-xs hover:border-accent"
          >
            <p className="truncate text-neutral-700">{run.question}</p>
            <p className="mt-0.5 text-neutral-400">
              {run.status} · {new Date(run.created_at).toLocaleString()}
            </p>
          </Link>
        </li>
      ))}
    </ul>
  );
}
