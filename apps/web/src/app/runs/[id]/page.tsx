"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { RunView } from "@/components/RunView";
import { useRun } from "@/lib/useRun";

/** docs/05_FRONTEND_UX.md's `/runs/[id]`: "reproducible run details."
 * Loads the run's persisted state directly and keeps watching it live over
 * SSE (in case it's still in progress), reusing the same RunView the /ask
 * page uses once a run has finished starting. */
export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const { snapshot, error, isSubmitting, answerClarification, cancel } = useRun(runId);

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-6 py-12">
      <div>
        <Link href="/ask" className="text-sm text-accent hover:underline">
          ← Ask a new question
        </Link>
        <p className="mt-2 text-sm font-semibold uppercase tracking-wide text-accent">Run</p>
        <h1 className="mt-1 text-xl font-bold text-neutral-900">
          {snapshot?.question ?? "Loading run…"}
        </h1>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-blocked/30 bg-red-50 p-4 text-sm text-blocked"
        >
          {error}
        </div>
      ) : null}

      {snapshot ? (
        <RunView
          snapshot={snapshot}
          isSubmitting={isSubmitting}
          onAnswerClarification={answerClarification}
          onCancel={cancel}
        />
      ) : null}
    </main>
  );
}
