import { render, screen } from "@testing-library/react";
import type { ValidatorOutput } from "@bi-copilot/contracts";
import { describe, expect, it } from "vitest";
import { ValidationBadge } from "@/components/ValidationBadge";

function validator(overrides: Partial<ValidatorOutput> = {}): ValidatorOutput {
  return {
    status: "pass",
    checks: [{ name: "sql_policy", status: "pass", details: "ok" }],
    repairable: false,
    feedback: null,
    result: null,
    ...overrides,
  };
}

describe("ValidationBadge", () => {
  it("renders nothing when there is no validator output yet", () => {
    const { container } = render(<ValidationBadge validator={null} />);

    expect(container.firstChild).toBeNull();
  });

  it("shows Validated for an all-pass result", () => {
    render(<ValidationBadge validator={validator()} />);

    expect(screen.getByText("Validated")).toBeInTheDocument();
  });

  it("shows a warning count when checks include a warning", () => {
    render(
      <ValidationBadge
        validator={validator({
          checks: [
            { name: "sql_policy", status: "pass", details: "ok" },
            { name: "result_row_limit", status: "warning", details: "truncated" },
          ],
        })}
      />,
    );

    expect(screen.getByText("Validated with warnings")).toBeInTheDocument();
    expect(screen.getByText("(1 warning)")).toBeInTheDocument();
  });

  it("shows Validation failed with a failure count", () => {
    render(
      <ValidationBadge
        validator={validator({
          status: "fail",
          checks: [{ name: "non_negative_columns", status: "fail", details: "negative value" }],
        })}
      />,
    );

    expect(screen.getByText("Validation failed")).toBeInTheDocument();
    expect(screen.getByText("(1 failed)")).toBeInTheDocument();
  });
});
