"use client";

import { useState } from "react";
import { QuestionComposer } from "@/components/QuestionComposer";
import { RunHistory } from "@/components/RunHistory";
import { RunView } from "@/components/RunView";
import { useRun } from "@/lib/useRun";

export default function AskPage() {
  const { snapshot, error, isSubmitting, start, answerClarification, cancel } = useRun();
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const handleAsk = async (question: string) => {
    await start(question);
    setHistoryRefreshKey((key) => key + 1);
  };

  return (
    <main className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 gap-8 px-6 py-12 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-accent">Ask</p>
          <h1 className="mt-1 text-2xl font-bold text-neutral-900">NL-to-Insight BI Copilot</h1>
        </div>

        <QuestionComposer onSubmit={handleAsk} isSubmitting={isSubmitting} />

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
        ) : !error ? (
          <p className="text-sm text-neutral-500">
            Ask a question above, or pick one from a past run.
          </p>
        ) : null}
      </div>

      <aside className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">History</h2>
        <RunHistory refreshKey={historyRefreshKey} />
      </aside>
    </main>
  );
}
