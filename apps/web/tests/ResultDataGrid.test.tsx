import { render, screen } from "@testing-library/react";
import type { QueryResult } from "@bi-copilot/contracts";
import { describe, expect, it } from "vitest";
import { ResultDataGrid } from "@/components/ResultDataGrid";

const RESULT: QueryResult = {
  columns: ["department_name", "median_hold_hrs"],
  rows: [
    ["Buyer", 9.5],
    ["Buyer", 27.4],
  ],
  row_count: 2,
  truncated: false,
};

describe("ResultDataGrid", () => {
  it("renders a header per column and a row per result row", () => {
    render(<ResultDataGrid result={RESULT} />);

    expect(screen.getByText("department_name")).toBeInTheDocument();
    expect(screen.getByText("9.5")).toBeInTheDocument();
    expect(screen.getByText("27.4")).toBeInTheDocument();
  });

  it("shows a no-rows message for an empty result", () => {
    render(<ResultDataGrid result={{ ...RESULT, rows: [], row_count: 0 }} />);

    expect(screen.getByText(/returned no rows/i)).toBeInTheDocument();
  });

  it("shows a truncation notice when the result was truncated", () => {
    render(<ResultDataGrid result={{ ...RESULT, truncated: true }} />);

    expect(screen.getByText(/more rows exist/i)).toBeInTheDocument();
  });

  it("highlights the cell matching a claim's evidence reference", () => {
    render(<ResultDataGrid result={RESULT} highlightedCells={new Set(["r2:c2"])} />);

    expect(screen.getByText("27.4")).toHaveClass("bg-accent-foreground");
    expect(screen.getByText("9.5")).not.toHaveClass("bg-accent-foreground");
  });
});
