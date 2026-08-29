import type { QueryResult } from "@bi-copilot/contracts";

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}

/** A single-row result is naturally KPI-shaped (one value per column); a
 * multi-row result is left to ResultDataGrid instead of forcing an
 * arbitrary subset of rows into tiles. */
export function KpiGrid({ result }: { result: QueryResult | null | undefined }) {
  if (!result || result.row_count !== 1) return null;
  const row = result.rows[0];
  if (!row) return null;

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {result.columns.map((column, index) => (
        <div key={column} className="rounded-lg border border-neutral-200 bg-white p-4">
          <dt className="text-xs font-medium uppercase tracking-wide text-neutral-500">{column}</dt>
          <dd className="mt-1 text-xl font-semibold text-neutral-900">{formatValue(row[index])}</dd>
        </div>
      ))}
    </dl>
  );
}
