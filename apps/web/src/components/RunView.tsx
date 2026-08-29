"use client";

import { useMemo, useState } from "react";
import type { RunSnapshot } from "@bi-copilot/contracts";
import { AgentProgress } from "@/components/AgentProgress";
import { ClarificationCard } from "@/components/ClarificationCard";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { InsightNarrative } from "@/components/InsightNarrative";
import { KpiGrid } from "@/components/KpiGrid";
import { ResultDataGrid } from "@/components/ResultDataGrid";
import { ValidationBadge } from "@/components/ValidationBadge";

interface Props {
  snapshot: RunSnapshot;
  isSubmitting?: boolean;
  onAnswerClarification: (answer: string) => void;
  onCancel: () => void;
}

const IN_PROGRESS_STATUSES: RunSnapshot["status"][] = [
  "RECEIVED",
  "RETRIEVING",
  "GENERATING_SQL",
  "VALIDATING",
  "REPAIR_SQL",
  "GENERATING_INSIGHT",
];

/** Renders whatever docs/05_FRONTEND_UX.md's "critical states" table calls
 * for given a run's current status: running progress, clarification,
 * validation-failed diagnostics, or the full success view (KPIs, narrative,
 * evidence, result table). Shared by /ask (a run just started) and
 * /runs/[id] (an existing run, possibly still in progress) so both render
 * identically once they have a RunSnapshot. */
export function RunView({ snapshot, isSubmitting, onAnswerClarification, onCancel }: Props) {
  const [selectedClaimIndex, setSelectedClaimIndex] = useState<number | null>(null);
  const latestAttempt = snapshot.attempts.at(-1) ?? null;
  const hasValidatedResult = latestAttempt?.validator.status === "pass";

  const highlightedCells = useMemo(() => {
    if (selectedClaimIndex === null || !snapshot.insight) return undefined;
    const claim = snapshot.insight.claims[selectedClaimIndex];
    if (!claim) return undefined;
    return new Set(claim.evidence.map((ref) => ref.replace(/^result:/, "")));
  }, [selectedClaimIndex, snapshot.insight]);

  return (
    <div className="space-y-6">
      {IN_PROGRESS_STATUSES.includes(snapshot.status) ? (
        <div className="flex items-center justify-between gap-4">
          <AgentProgress status={snapshot.status} />
          <button
            type="button"
            onClick={onCancel}
            className="shrink-0 text-xs text-neutral-500 underline hover:text-blocked"
          >
            Cancel
          </button>
        </div>
      ) : null}

      {snapshot.status === "NEEDS_CLARIFICATION" && snapshot.clarification_question ? (
        <ClarificationCard
          question={snapshot.clarification_question}
          options={snapshot.clarification_options}
          onSubmit={onAnswerClarification}
          isSubmitting={isSubmitting}
        />
      ) : null}

      {snapshot.status === "FAILED" ? (
        <div className="rounded-lg border border-blocked/30 bg-red-50 p-4 text-sm text-neutral-700">
          <p className="font-medium text-blocked">This run could not produce a validated answer.</p>
          <p className="mt-1">{snapshot.error}</p>
          <p className="mt-2 text-xs text-neutral-500">Run ID: {snapshot.run_id}</p>
        </div>
      ) : null}

      {snapshot.status === "CANCELLED" ? (
        <p className="text-sm text-neutral-500">Run cancelled.</p>
      ) : null}

      {hasValidatedResult ? (
        <>
          <ValidationBadge validator={latestAttempt?.validator} />
          <KpiGrid result={latestAttempt?.validator.result} />
          <InsightNarrative
            insight={snapshot.insight}
            insightError={snapshot.insight_error}
            selectedClaimIndex={selectedClaimIndex}
            onClaimSelect={(index) =>
              setSelectedClaimIndex((current) => (current === index ? null : index))
            }
          />
          <ResultDataGrid
            result={latestAttempt?.validator.result}
            highlightedCells={highlightedCells}
          />
          <EvidenceDrawer snapshot={snapshot} />
        </>
      ) : null}
    </div>
  );
}
