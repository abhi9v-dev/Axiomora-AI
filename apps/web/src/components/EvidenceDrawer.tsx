import type { RunSnapshot } from "@bi-copilot/contracts";
import { SqlViewer } from "@/components/SqlViewer";

/** docs/05_FRONTEND_UX.md: "collapsible 'Evidence & SQL' panel containing
 * retrieved definitions, assumptions, SQL and checks." Always shows the
 * most recent attempt -- the one that actually produced the current
 * result/insight (or, on a failed run, the one whose feedback explains why). */
export function EvidenceDrawer({ snapshot }: { snapshot: RunSnapshot }) {
  const latestAttempt = snapshot.attempts.at(-1);

  return (
    <details className="rounded-lg border border-neutral-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-neutral-700">
        Evidence &amp; SQL
      </summary>
      <div className="mt-4 space-y-4 text-sm">
        {snapshot.retrieved_context.length > 0 ? (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Retrieved definitions
            </h3>
            <ul className="mt-1 space-y-1">
              {snapshot.retrieved_context.map((item) => (
                <li key={item.citation} className="text-neutral-600">
                  <span className="font-medium text-neutral-800">{item.object_name}</span> —{" "}
                  {item.title}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {latestAttempt ? (
          <>
            {latestAttempt.nl2sql.assumptions.length > 0 ? (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                  Assumptions
                </h3>
                <ul className="mt-1 list-disc pl-5 text-neutral-600">
                  {latestAttempt.nl2sql.assumptions.map((assumption) => (
                    <li key={assumption}>{assumption}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                SQL
              </h3>
              <SqlViewer sql={latestAttempt.nl2sql.sql} />
            </div>

            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                Validation checks
              </h3>
              <ul className="mt-1 space-y-1">
                {latestAttempt.validator.checks.map((check) => (
                  <li key={check.name} className="flex items-start gap-2 text-neutral-600">
                    <span aria-hidden="true">
                      {check.status === "pass" ? "✓" : check.status === "warning" ? "⚠" : "✕"}
                    </span>
                    <span>
                      <span className="font-medium text-neutral-800">{check.name}:</span>{" "}
                      {check.details}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}
      </div>
    </details>
  );
}
