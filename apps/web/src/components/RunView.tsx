"use client";

import { useMemo, useState } from "react";
import type { RunSnapshot } from "@bi-copilot/contracts";
import { AgentProgress } from "@/components/AgentProgress";
import { ActionDialog } from "@/components/ActionDialog";
import { ClarificationCard } from "@/components/ClarificationCard";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { InsightNarrative } from "@/components/InsightNarrative";
import { KpiGrid } from "@/components/KpiGrid";
import { ResultDataGrid } from "@/components/ResultDataGrid";
import { ValidationBadge } from "@/components/ValidationBadge";
import { requestExcelExport, requestPowerBiAction, triggerBrowserDownload } from "@/lib/api";
import { getApiBaseUrl, isPowerBiEnabled } from "@/lib/env";

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
  const baseUrl = getApiBaseUrl();
  const [selectedClaimIndex, setSelectedClaimIndex] = useState<number | null>(null);
  const [isExportDialogOpen, setIsExportDialogOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [powerBiAction, setPowerBiAction] = useState<"power_bi_push" | "power_bi_refresh" | null>(
    null,
  );
  const [isPowerBiSubmitting, setIsPowerBiSubmitting] = useState(false);
  const [powerBiError, setPowerBiError] = useState<string | null>(null);
  const [powerBiSuccess, setPowerBiSuccess] = useState<string | null>(null);
  const latestAttempt = snapshot.attempts.at(-1) ?? null;
  const hasValidatedResult = latestAttempt?.validator.status === "pass";

  const handleExportConfirm = async () => {
    setIsExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await requestExcelExport(baseUrl, snapshot.run_id);
      triggerBrowserDownload(blob, filename);
      setIsExportDialogOpen(false);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Failed to export the workbook.");
    } finally {
      setIsExporting(false);
    }
  };

  const openPowerBiDialog = (type: "power_bi_push" | "power_bi_refresh") => {
    setPowerBiError(null);
    setPowerBiSuccess(null);
    setPowerBiAction(type);
  };

  const handlePowerBiConfirm = async () => {
    if (!powerBiAction) return;
    setIsPowerBiSubmitting(true);
    setPowerBiError(null);
    try {
      const result = await requestPowerBiAction(baseUrl, snapshot.run_id, powerBiAction);
      setPowerBiSuccess(result.detail ?? "The Power BI action completed.");
      setPowerBiAction(null);
    } catch (err) {
      setPowerBiError(err instanceof Error ? err.message : "The Power BI action failed.");
    } finally {
      setIsPowerBiSubmitting(false);
    }
  };

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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ValidationBadge validator={latestAttempt?.validator} />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setExportError(null);
                  setIsExportDialogOpen(true);
                }}
                className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:border-accent hover:text-accent"
              >
                Export Excel
              </button>
              {isPowerBiEnabled() ? (
                <>
                  <button
                    type="button"
                    onClick={() => openPowerBiDialog("power_bi_push")}
                    className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:border-accent hover:text-accent"
                  >
                    Publish to Power BI
                  </button>
                  <button
                    type="button"
                    onClick={() => openPowerBiDialog("power_bi_refresh")}
                    className="rounded-md border border-neutral-300 px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:border-accent hover:text-accent"
                  >
                    Refresh Power BI Dataset
                  </button>
                </>
              ) : null}
            </div>
          </div>
          {powerBiSuccess ? (
            <p role="status" className="text-sm text-verified">
              {powerBiSuccess}
            </p>
          ) : null}
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

      {isExportDialogOpen ? (
        <ActionDialog
          dataTimestamp={snapshot.completed_at}
          isSubmitting={isExporting}
          error={exportError}
          onConfirm={handleExportConfirm}
          onCancel={() => setIsExportDialogOpen(false)}
        />
      ) : null}

      {powerBiAction === "power_bi_push" ? (
        <ActionDialog
          dataTimestamp={snapshot.completed_at}
          title="Publish to Power BI"
          destination="Power BI dataset (push rows)"
          effect="Adds new rows to the configured Power BI dataset table; does not remove or overwrite existing rows."
          confirmLabel="Publish"
          submittingLabel="Publishing…"
          isSubmitting={isPowerBiSubmitting}
          error={powerBiError}
          onConfirm={handlePowerBiConfirm}
          onCancel={() => setPowerBiAction(null)}
        />
      ) : null}

      {powerBiAction === "power_bi_refresh" ? (
        <ActionDialog
          dataTimestamp={snapshot.completed_at}
          title="Refresh Power BI dataset"
          destination="Power BI dataset refresh"
          effect="Triggers Power BI to reload the dataset from its configured source; this may replace previously loaded data in Power BI (not in the warehouse)."
          confirmLabel="Refresh"
          submittingLabel="Refreshing…"
          isSubmitting={isPowerBiSubmitting}
          error={powerBiError}
          onConfirm={handlePowerBiConfirm}
          onCancel={() => setPowerBiAction(null)}
        />
      ) : null}
    </div>
  );
}
