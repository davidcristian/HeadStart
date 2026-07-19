import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import { PortalCategoryFilters } from "./PortalCategoryFilters";

describe("PortalCategoryFilters", () => {
  it("exposes a labelled button group with aria-pressed, not a tablist", () => {
    const onChange = vi.fn();
    renderWithClient(
      <PortalCategoryFilters category="" categories={["unicorn", "ai"]} onChange={onChange} />,
    );

    expect(screen.getByRole("group", { name: "Portal categories" })).toBeInTheDocument();
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();

    const all = screen.getByRole("button", { name: "All" });
    const unicorns = screen.getByRole("button", { name: "Unicorns" });
    expect(all).toHaveAttribute("aria-pressed", "true");
    expect(unicorns).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(unicorns);
    expect(onChange).toHaveBeenCalledWith("unicorn");
  });

  it("marks the active category as pressed", () => {
    renderWithClient(
      <PortalCategoryFilters category="ai" categories={["big_tech", "ai"]} onChange={vi.fn()} />,
    );

    expect(screen.getByRole("button", { name: "AI" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "AI" })).toHaveClass("active");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "All" })).not.toHaveClass("active");
  });
});
