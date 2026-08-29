interface Props {
  dataTimestamp: string | null;
  title?: string;
  destination?: string;
  effect?: string;
  confirmLabel?: string;
  submittingLabel?: string;
  isSubmitting?: boolean;
  error?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}

/** docs/07_SECURITY_GOVERNANCE.md: "the confirmation dialog must identify
 * destination, effect, data timestamp and whether existing content
 * changes." Defaults match Excel export's copy (docs/07's action policy
 * table: "Download Excel -- Allowed for result owner -- User click"),
 * which needs no destination-specific approval beyond this click; the
 * Power BI actions (Phase 8) pass their own title/destination/effect/
 * confirmLabel instead, reusing this same shape. */
export function ActionDialog({
  dataTimestamp,
  title = "Export to Excel",
  destination = "Download to your device",
  effect = "Creates a new file; nothing existing is changed or overwritten.",
  confirmLabel = "Download",
  submittingLabel = "Exporting…",
  isSubmitting,
  error,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="action-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-sm rounded-lg bg-white p-5 shadow-lg">
        <h2 id="action-dialog-title" className="text-base font-semibold text-neutral-900">
          {title}
        </h2>
        <dl className="mt-3 space-y-2 text-sm text-neutral-600">
          <div>
            <dt className="font-medium text-neutral-700">Destination</dt>
            <dd>{destination}</dd>
          </div>
          <div>
            <dt className="font-medium text-neutral-700">Effect</dt>
            <dd>{effect}</dd>
          </div>
          <div>
            <dt className="font-medium text-neutral-700">Data as of</dt>
            <dd>{dataTimestamp ? new Date(dataTimestamp).toLocaleString() : "unknown"}</dd>
          </div>
        </dl>

        {error ? (
          <p role="alert" className="mt-3 text-sm text-blocked">
            {error}
          </p>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm text-neutral-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSubmitting}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-accent-foreground disabled:opacity-50"
          >
            {isSubmitting ? submittingLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
