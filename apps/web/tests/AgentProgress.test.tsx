import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AgentProgress } from "@/components/AgentProgress";

describe("AgentProgress", () => {
  it("marks the current step and earlier steps as done", () => {
    render(<AgentProgress status="VALIDATING" />);

    expect(screen.getByText("Validating").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Writing SQL").closest("li")).toHaveTextContent("✓");
    expect(screen.getByText("Explaining").closest("li")).not.toHaveTextContent("✓");
  });

  it("shows a repair hint during REPAIR_SQL", () => {
    render(<AgentProgress status="REPAIR_SQL" />);

    expect(screen.getByText(/repairing the sql/i)).toBeInTheDocument();
  });

  it("renders nothing for a terminal status", () => {
    const { container } = render(<AgentProgress status="READY" />);

    // READY still renders the stepper (all steps done); truly terminal/paused
    // statuses like NEEDS_CLARIFICATION render nothing -- RunView shows its
    // own state instead.
    expect(container.querySelector("ol")).not.toBeNull();
  });

  it("renders nothing when awaiting clarification", () => {
    const { container } = render(<AgentProgress status="NEEDS_CLARIFICATION" />);

    expect(container.firstChild).toBeNull();
  });
});
