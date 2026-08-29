import type { InsightOutput } from "@bi-copilot/contracts";

interface Props {
  insight: InsightOutput | null | undefined;
  insightError?: string | null;
  onClaimSelect?: (index: number) => void;
  selectedClaimIndex?: number | null;
}

/** docs/05_FRONTEND_UX.md: "narrative section with numbered claims;
 * clicking a claim highlights supporting cells" -- the highlight itself
 * lives in ResultDataGrid, driven by the parent page's selection state. */
export function InsightNarrative({
  insight,
  insightError,
  onClaimSelect,
  selectedClaimIndex,
}: Props) {
  if (insightError) {
    return (
      <div className="rounded-lg border border-warning/30 bg-amber-50 p-4 text-sm text-neutral-700">
        <p className="font-medium text-warning">The narrative could not be generated.</p>
        <p className="mt-1">
          {insightError} The validated result and SQL below are still available.
        </p>
      </div>
    );
  }

  if (!insight) return null;

  return (
    <section aria-label="Insight" className="space-y-3">
      <h2 className="text-lg font-semibold text-neutral-900">{insight.headline}</h2>
      <p className="text-neutral-700">{insight.narrative}</p>
      {insight.claims.length > 0 ? (
        <ol className="space-y-1">
          {insight.claims.map((claim, index) => (
            <li key={claim.text}>
              <button
                type="button"
                onClick={() => onClaimSelect?.(index)}
                aria-pressed={selectedClaimIndex === index}
                className={`w-full rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                  selectedClaimIndex === index
                    ? "border-accent bg-accent-foreground"
                    : "border-neutral-200 bg-white hover:border-accent"
                }`}
              >
                <span className="mr-2 font-semibold text-accent">{index + 1}.</span>
                {claim.text}
              </button>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
