import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActionDialog } from "@/components/ActionDialog";

describe("ActionDialog", () => {
  it("shows destination, effect and the data timestamp", () => {
    render(
      <ActionDialog dataTimestamp="2026-08-30T12:00:00Z" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );

    expect(screen.getByText("Download to your device")).toBeInTheDocument();
    expect(screen.getByText(/nothing existing is changed/i)).toBeInTheDocument();
    expect(screen.getByText(new Date("2026-08-30T12:00:00Z").toLocaleString())).toBeInTheDocument();
  });

  it("calls onConfirm and onCancel", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ActionDialog dataTimestamp={null} onConfirm={onConfirm} onCancel={onCancel} />);

    await user.click(screen.getByRole("button", { name: "Download" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables the Download button while submitting", () => {
    render(
      <ActionDialog dataTimestamp={null} isSubmitting onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: /exporting/i })).toBeDisabled();
  });

  it("shows unknown when no data timestamp is available", () => {
    render(<ActionDialog dataTimestamp={null} onConfirm={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});
