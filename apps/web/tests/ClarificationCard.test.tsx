import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ClarificationCard } from "@/components/ClarificationCard";

describe("ClarificationCard", () => {
  it("submits the selected option", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <ClarificationCard
        question="Which department?"
        options={["Buyer", "Supplier"]}
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByLabelText("Buyer"));
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onSubmit).toHaveBeenCalledWith("Buyer");
  });

  it("submits free text when no option is selected", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ClarificationCard question="Which department?" options={null} onSubmit={onSubmit} />);

    await user.type(screen.getByRole("textbox"), "The Buyer department");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    expect(onSubmit).toHaveBeenCalledWith("The Buyer department");
  });

  it("disables submit until an answer is provided", () => {
    render(<ClarificationCard question="Which department?" options={null} onSubmit={vi.fn()} />);

    expect(screen.getByRole("button", { name: /continue/i })).toBeDisabled();
  });
});
