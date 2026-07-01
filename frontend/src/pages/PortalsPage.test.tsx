import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleTarget } from "../test/fixtures";
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
});
