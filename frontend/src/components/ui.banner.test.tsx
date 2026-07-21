import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Banner } from "./ui";

describe("Banner live regions", () => {
  it("announces errors assertively", () => {
    render(<Banner kind="error">Boom</Banner>);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(alert).toHaveTextContent("Boom");
  });

  it("announces info and success politely", () => {
    const { rerender } = render(<Banner kind="info">Heads up</Banner>);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("status")).toHaveTextContent("Heads up");

    rerender(<Banner kind="success">Done</Banner>);
    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
    expect(screen.getByRole("status")).toHaveTextContent("Done");
  });
});
