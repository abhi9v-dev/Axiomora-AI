import type { QueryResult } from "@bi-copilot/contracts";

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

interface Props {
  result: QueryResult | null | undefined;
  /** 1-indexed "r{row}:c{col}" keys (the evidence cell ID minus its
   * "result:" prefix) to highlight -- set when a claim in InsightNarrative
   * is selected. */
  highlightedCells?: Set<string>;
}

export function ResultDataGrid({ result, highlightedCells }: Props) {
  if (!result) return null;

  if (result.row_count === 0) {
    return <p className="text-sm text-neutral-500">The query returned no rows.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-neutral-200">
      <table className="min-w-full divide-y divide-neutral-200 text-sm">
        <thead className="bg-neutral-50">
          <tr>
            {result.columns.map((column) => (
              <th
                key={column}
                scope="col"
                className="whitespace-nowrap px-3 py-2 text-left font-semibold text-neutral-600"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100 font-mono">
          {result.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((value, colIndex) => {
                const cellKey = `r${rowIndex + 1}:c${colIndex + 1}`;
                const highlighted = highlightedCells?.has(cellKey);
                return (
                  <td
                    key={colIndex}
                    className={`whitespace-nowrap px-3 py-2 ${
                      highlighted
                        ? "bg-accent-foreground font-semibold text-accent"
                        : "text-neutral-700"
                    }`}
                  >
                    {formatValue(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {result.truncated ? (
        <p className="border-t border-neutral-200 bg-neutral-50 px-3 py-2 text-xs text-neutral-500">
          Showing the first {result.row_count.toLocaleString()} row(s); more rows exist.
        </p>
      ) : null}
    </div>
  );
}
