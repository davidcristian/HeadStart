import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PortalSearchResult } from "../../types";
import { renderWithClient } from "../../test/renderWithClient";
import { PortalsResultsCard } from "./PortalsResultsCard";

function makeResult(overrides: Partial<PortalSearchResult> = {}): PortalSearchResult {
  return {
    items: [],
    portals_searched: 1,
    portals_failed: 0,
    errors: [],
    ...overrides,
  };
}

describe("PortalsResultsCard", () => {
  it("shows the empty state and singular portal wording", () => {
    renderWithClient(<PortalsResultsCard results={makeResult({ portals_searched: 1 })} />);

    expect(screen.getByRole("heading", { name: "Results (0)" })).toBeInTheDocument();
    expect(screen.getByText(/Searched 1 portal\./)).toBeInTheDocument();
    expect(
      screen.getByText(/No matching jobs right now. Try broader keywords or more companies./),
    ).toBeInTheDocument();
  });

  it("pluralizes portals and reports failures plus errors", () => {
    renderWithClient(
      <PortalsResultsCard
        results={makeResult({
          portals_searched: 3,
          portals_failed: 2,
          errors: [{ portal_id: "stripe", company_name: "Stripe", error: "boom" }],
        })}
      />,
    );

    expect(
      screen.getByText(/Searched 3 portals; 2 failed \(see errors below\)\./),
    ).toBeInTheDocument();
    expect(screen.getByText("Stripe:")).toBeInTheDocument();
    expect(screen.getByText(/boom/)).toBeInTheDocument();
  });

  it("renders job rows with and without a location and a link", () => {
    renderWithClient(
      <PortalsResultsCard
        results={makeResult({
          items: [
            {
              portal_id: "stripe",
              company_name: "Stripe",
              external_id: "1",
              title: "Software Engineer",
              location: "Remote",
              url: "https://example.com/jobs/1",
            },
            {
              portal_id: "meta",
              company_name: "Meta",
              external_id: "2",
              title: "Frontend Engineer",
              location: "",
              url: "",
            },
          ],
        })}
      />,
    );

    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText(/Stripe · Remote/)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "View" });
    expect(link).toHaveAttribute("href", "https://example.com/jobs/1");

    // Second row has no url so no link, and no " · location" suffix.
    expect(screen.getByText("Frontend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Meta")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
