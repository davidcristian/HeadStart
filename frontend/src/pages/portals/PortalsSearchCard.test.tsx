import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Portal } from "../../types";
import { renderWithClient } from "../../test/renderWithClient";
import { PortalsSearchCard } from "./PortalsSearchCard";

type Props = Parameters<typeof PortalsSearchCard>[0];

function makePortal(id: string): Portal {
  return {
    id,
    company_name: id,
    category: "unicorn",
    adapter_key: "greenhouse",
    base_url: `https://boards.greenhouse.io/${id}`,
    default_config: {},
    supports_auto_apply: false,
    allowed_on_plan: true,
    already_added: false,
  };
}

function renderCard(overrides: Partial<Props> = {}) {
  const props: Props = {
    category: "",
    setCategory: vi.fn(),
    categories: ["big_tech", "unicorn", "ai"],
    keywords: "",
    setKeywords: vi.fn(),
    location: "",
    setLocation: vi.fn(),
    workplace: "",
    setWorkplace: vi.fn(),
    catalogItems: [makePortal("stripe"), makePortal("meta")],
    selectedIds: new Set(["stripe"]),
    setSelectedIds: vi.fn(),
    togglePortal: vi.fn(),
    portalsPending: false,
    portalsError: false,
    onSearch: vi.fn(),
    searchPending: false,
    ...overrides,
  };
  const utils = renderWithClient(<PortalsSearchCard {...props} />);
  return { props, ...utils };
}

describe("PortalsSearchCard", () => {
  it("renders the catalog, toolbar counts, and category tabs", () => {
    const { props } = renderCard();

    expect(screen.getByText("1 of 2 selected")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "All" }));
    expect(props.setCategory).toHaveBeenCalledWith("");

    fireEvent.click(screen.getByRole("tab", { name: "Big tech" }));
    expect(props.setCategory).toHaveBeenCalledWith("big_tech");
  });

  it("wires keyword, location, and workplace inputs", () => {
    const { props } = renderCard();

    fireEvent.change(screen.getByPlaceholderText("software engineer"), {
      target: { value: "engineer" },
    });
    expect(props.setKeywords).toHaveBeenCalledWith("engineer");

    fireEvent.change(screen.getByPlaceholderText("remote, san francisco"), {
      target: { value: "remote" },
    });
    expect(props.setLocation).toHaveBeenCalledWith("remote");

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "hybrid" } });
    expect(props.setWorkplace).toHaveBeenCalledWith("hybrid");
  });

  it("select all and clear update the selection", () => {
    const { props } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(props.setSelectedIds).toHaveBeenCalledWith(new Set(["stripe", "meta"]));

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(props.setSelectedIds).toHaveBeenCalledWith(new Set());
  });

  it("toggles an individual portal and runs the search", () => {
    const { props } = renderCard();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);
    expect(props.togglePortal).toHaveBeenCalledWith("meta");

    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));
    expect(props.onSearch).toHaveBeenCalledTimes(1);
  });

  it("reflects the active category tab styling", () => {
    renderCard({ category: "ai" });
    expect(screen.getByRole("tab", { name: "AI" })).toHaveClass("active");
    expect(screen.getByRole("tab", { name: "All" })).not.toHaveClass("active");
  });

  it("shows the loading state while portals are pending", () => {
    renderCard({ portalsPending: true, catalogItems: [] });
    expect(screen.getByText("Loading companies...")).toBeInTheDocument();
    // Empty state is suppressed while pending.
    expect(
      screen.queryByText("No companies available on your plan for this filter."),
    ).not.toBeInTheDocument();
  });

  it("shows the error banner when the catalog fails to load", () => {
    renderCard({ portalsError: true });
    expect(screen.getByText("Could not load the company catalog.")).toBeInTheDocument();
  });

  it("shows the empty state when no companies are available", () => {
    renderCard({ catalogItems: [] });
    expect(
      screen.getByText("No companies available on your plan for this filter."),
    ).toBeInTheDocument();
  });

  it("disables the search button and shows the pending label while searching", () => {
    renderCard({ searchPending: true });
    expect(screen.getByRole("button", { name: "Searching..." })).toBeDisabled();
  });
});
