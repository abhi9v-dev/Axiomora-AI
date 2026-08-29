import type { ValidatorOutput } from "@bi-copilot/contracts";

/** Status communicated by text/icon, not color alone
 * (docs/05_FRONTEND_UX.md's accessibility rule). */
export function ValidationBadge({ validator }: { validator: ValidatorOutput | undefined | null }) {
  if (!validator) return null;

  const failed = validator.checks.filter((check) => check.status === "fail").length;
  const warned = validator.checks.filter((check) => check.status === "warning").length;

  const tone = validator.status === "fail" ? "blocked" : warned > 0 ? "warning" : "verified";
  const label =
    validator.status === "fail"
      ? "Validation failed"
      : warned > 0
        ? "Validated with warnings"
        : "Validated";
  const icon = tone === "blocked" ? "✕" : tone === "warning" ? "⚠" : "✓";

  const toneClasses =
    tone === "blocked"
      ? "border-blocked/30 bg-red-50 text-blocked"
      : tone === "warning"
        ? "border-warning/30 bg-amber-50 text-warning"
        : "border-verified/30 bg-green-50 text-verified";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${toneClasses}`}
    >
      <span aria-hidden="true">{icon}</span>
      {label}
      {failed + warned > 0 ? (
        <span className="font-normal opacity-80">
          (
          {[failed ? `${failed} failed` : null, warned ? `${warned} warning` : null]
            .filter(Boolean)
            .join(", ")}
          )
        </span>
      ) : null}
    </span>
  );
}
