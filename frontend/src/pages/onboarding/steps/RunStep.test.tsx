import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../../../test/renderWithClient";
import { RunStep } from "./RunStep";

describe("RunStep", () => {
  it("runs the search and completes when a search exists", () => {
    const onRun = vi.fn();
    const onComplete = vi.fn();
    renderWithClient(<RunStep busy={false} searchId={20} onRun={onRun} onComplete={onComplete} />);

    const runButton = screen.getByRole("button", { name: "Run now" });
    expect(runButton).toBeEnabled();
    fireEvent.click(runButton);
    expect(onRun).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Go to Jobs" }));
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("disables run when there is no search id", () => {
    renderWithClient(<RunStep busy={false} searchId={null} onRun={vi.fn()} onComplete={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Run now" })).toBeDisabled();
  });

  it("shows the running label and disables both buttons while busy", () => {
    renderWithClient(<RunStep busy={true} searchId={20} onRun={vi.fn()} onComplete={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Running..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Go to Jobs" })).toBeDisabled();
  });
});
