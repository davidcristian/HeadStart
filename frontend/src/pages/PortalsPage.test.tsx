import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleAccountPlan, sampleMeta, sampleTarget } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { PortalsPage } from "./PortalsPage";

function renderPage() {
  return renderWithClient(
    <MemoryRouter>
      <PortalsPage />
    </MemoryRouter>,
  );
}

describe("PortalsPage", () => {
  beforeEach(() => {
    resetMockApi();
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
  });

  it("renders the company search page for Pro users", async () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Company search" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Stripe")).toBeInTheDocument());
  });

  it("runs a cross-portal search", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Stripe")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("software engineer"), {
      target: { value: "engineer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));

    await waitFor(() => expect(mockApi.searchPortals).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
  });

  it("shows the upgrade prompt when portal search is not on the plan", async () => {
    mockApi.meta.mockResolvedValue({
      ...sampleMeta,
      plan: {
        ...sampleAccountPlan,
        plan: "free",
        effective_plan: "free",
        features: { ...sampleAccountPlan.features, portal_search: false },
      },
    });
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/Upgrade\s+to Pro to unlock cross-portal search/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "View pricing" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Search jobs" })).not.toBeInTheDocument();
  });

  it("shows an error banner when searching without keywords", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Stripe")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Search jobs" }));

    await waitFor(() =>
      expect(
        screen.getByText("Enter keywords to search across company portals."),
      ).toBeInTheDocument(),
    );
  });

  it("shows a success notice after creating alerts", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Stripe")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("software engineer"), {
      target: { value: "engineer" },
    });
    fireEvent.change(screen.getByDisplayValue("Select target"), {
      target: { value: String(sampleTarget.id) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create alerts" }));

    await waitFor(() => expect(mockApi.subscribePortals).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByText("Created 1 search; added 1 source.")).toBeInTheDocument(),
    );
  });
});
