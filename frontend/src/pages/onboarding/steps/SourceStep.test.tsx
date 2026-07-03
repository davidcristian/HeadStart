import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../../test/renderWithClient";
import { SourceStep } from "./SourceStep";

type Props = Parameters<typeof SourceStep>[0];

function renderStep(overrides: Partial<Props> = {}) {
  const props: Props = {
    busy: false,
    detectUrl: "https://boards.greenhouse.io/acme",
    sourceName: "ACME",
    baseUrl: "https://boards.greenhouse.io/acme",
    effectiveAdapter: "greenhouse",
    adapters: ["greenhouse", "lever"],
    onDetectUrlChange: vi.fn(),
    onSourceNameChange: vi.fn(),
    onBaseUrlChange: vi.fn(),
    onAdapterChange: vi.fn(),
    onDetect: vi.fn((e) => e.preventDefault()),
    onSubmit: vi.fn((e) => e.preventDefault()),
    onBack: vi.fn(),
    ...overrides,
  };
  const utils = renderWithClient(<SourceStep {...props} />);
  return { props, ...utils };
}

describe("SourceStep", () => {
  it("renders adapter options and edits every field", () => {
    const { props } = renderStep();

    expect(screen.getByRole("option", { name: "greenhouse" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "lever" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Careers or search URL"), {
      target: { value: "https://new.test" },
    });
    expect(props.onDetectUrlChange).toHaveBeenCalledWith("https://new.test");

    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "New Co" } });
    expect(props.onSourceNameChange).toHaveBeenCalledWith("New Co");

    fireEvent.change(screen.getByLabelText("Base URL"), { target: { value: "https://b.test" } });
    expect(props.onBaseUrlChange).toHaveBeenCalledWith("https://b.test");

    fireEvent.change(screen.getByLabelText("Scraper"), { target: { value: "lever" } });
    expect(props.onAdapterChange).toHaveBeenCalledWith("lever");
  });

  it("detects, submits, and goes back", () => {
    const { props } = renderStep();

    fireEvent.click(screen.getByRole("button", { name: "Detect board" }));
    expect(props.onDetect).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(props.onSubmit).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(props.onBack).toHaveBeenCalledTimes(1);
  });

  it("disables the detect button when the URL is blank and continue while busy", () => {
    renderStep({ detectUrl: "   ", busy: true });
    expect(screen.getByRole("button", { name: "Detect board" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });
});
