import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../../test/renderWithClient";
import { TargetStep } from "./TargetStep";

type Props = Parameters<typeof TargetStep>[0];

function renderStep(overrides: Partial<Props> = {}) {
  const props: Props = {
    busy: false,
    targetName: "My phone",
    effectiveNotifier: "ntfy",
    notifiers: ["ntfy", "email"],
    notifierConfig: { topic: "job-alerts" },
    onTargetNameChange: vi.fn(),
    onNotifierTypeChange: vi.fn(),
    onNotifierConfigChange: vi.fn(),
    onSubmit: vi.fn((e) => e.preventDefault()),
    onBack: vi.fn(),
    ...overrides,
  };
  const utils = renderWithClient(<TargetStep {...props} />);
  return { props, ...utils };
}

describe("TargetStep", () => {
  it("renders notifier options and edits name and channel", () => {
    const { props } = renderStep();

    expect(screen.getByRole("option", { name: "ntfy" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "email" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Work laptop" },
    });
    expect(props.onTargetNameChange).toHaveBeenCalledWith("Work laptop");

    fireEvent.change(screen.getByLabelText("Channel"), {
      target: { value: "email" },
    });
    expect(props.onNotifierTypeChange).toHaveBeenCalledWith("email");
  });

  it("forwards notifier config changes from the dynamic fields", () => {
    const { props } = renderStep();

    fireEvent.change(screen.getByPlaceholderText("my-job-alerts"), {
      target: { value: "new-topic" },
    });
    expect(props.onNotifierConfigChange).toHaveBeenCalledWith({
      topic: "new-topic",
    });
  });

  it("submits and goes back", () => {
    const { props } = renderStep();

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(props.onSubmit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(props.onBack).toHaveBeenCalledTimes(1);
  });

  it("disables continue while busy", () => {
    renderStep({ busy: true });
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});
