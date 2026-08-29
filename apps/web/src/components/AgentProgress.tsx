import type { RunStatus } from "@bi-copilot/contracts";

const STEPS: { status: RunStatus; label: string }[] = [
  { status: "RECEIVED", label: "Understanding" },
  { status: "RETRIEVING", label: "Finding schema" },
  { status: "GENERATING_SQL", label: "Writing SQL" },
  { status: "VALIDATING", label: "Validating" },
  { status: "GENERATING_INSIGHT", label: "Explaining" },
];

const STEP_INDEX: Record<RunStatus, number> = {
  RECEIVED: 0,
  RETRIEVING: 1,
  GENERATING_SQL: 2,
  REPAIR_SQL: 2,
  VALIDATING: 3,
  GENERATING_INSIGHT: 4,
  READY: 5,
  NEEDS_CLARIFICATION: -1,
  FAILED: -1,
  CANCELLED: -1,
};

/** docs/05_FRONTEND_UX.md: "streaming stepper... no fake percentages" --
 * each step reflects a real state transition already received over SSE,
 * never a synthetic progress estimate. */
export function AgentProgress({ status }: { status: RunStatus }) {
  const currentIndex = STEP_INDEX[status];
  if (currentIndex < 0) return null;

  return (
    <div>
      <ol aria-label="Answer progress" className="flex flex-wrap gap-2">
        {STEPS.map((step, index) => {
          const done = currentIndex > index || status === "READY";
          const active = currentIndex === index && status !== "READY";
          return (
            <li
              key={step.status}
              aria-current={active ? "step" : undefined}
              className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
                done
                  ? "border-verified/30 bg-green-50 text-verified"
                  : active
                    ? "border-accent bg-accent-foreground text-accent"
                    : "border-neutral-200 text-neutral-400"
              }`}
            >
              <span aria-hidden="true">{done ? "✓" : active ? "●" : "○"}</span>
              {step.label}
            </li>
          );
        })}
      </ol>
      {status === "REPAIR_SQL" ? (
        <p className="mt-2 text-xs text-warning">Repairing the SQL based on validator feedback…</p>
      ) : null}
    </div>
  );
}
