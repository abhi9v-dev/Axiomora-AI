import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { InsightOutput } from "@bi-copilot/contracts";
import { describe, expect, it, vi } from "vitest";
import { InsightNarrative } from "@/components/InsightNarrative";

const INSIGHT: InsightOutput = {
  headline: "Buyer median hold time rose in Q2",
  narrative: "Driven by Supplier Compliance Review tasks.",
  claims: [
    {
      text: "Median hold time moved from 9.5 to 27.4 hours",
      evidence: ["result:r1:c3", "result:r2:c3"],
    },
  ],
  chart: null,
};

describe("InsightNarrative", () => {
  it("renders the headline, narrative and numbered claims", () => {
    render(<InsightNarrative insight={INSIGHT} />);

    expect(screen.getByText(INSIGHT.headline)).toBeInTheDocument();
    expect(screen.getByText(INSIGHT.narrative)).toBeInTheDocument();
    expect(screen.getByText(/median hold time moved/i)).toBeInTheDocument();
  });

  it("calls onClaimSelect with the claim's index when clicked", async () => {
    const user = userEvent.setup();
    const onClaimSelect = vi.fn();
    render(<InsightNarrative insight={INSIGHT} onClaimSelect={onClaimSelect} />);

    await user.click(screen.getByText(/median hold time moved/i));

    expect(onClaimSelect).toHaveBeenCalledWith(0);
  });

  it("shows an explanatory message instead of a narrative when generation failed", () => {
    render(<InsightNarrative insight={null} insightError="model outage" />);

    expect(screen.getByText(/could not be generated/i)).toBeInTheDocument();
    expect(screen.getByText(/model outage/)).toBeInTheDocument();
  });

  it("renders nothing when there is no insight and no error", () => {
    const { container } = render(<InsightNarrative insight={null} />);

    expect(container.firstChild).toBeNull();
  });
});
