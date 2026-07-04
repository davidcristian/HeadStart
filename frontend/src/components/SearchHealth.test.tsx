import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sampleSearch } from "../test/fixtures";
import { SearchHealthBadge, SearchHealthDetails, SearchLastRun } from "./SearchHealth";
import type { DeliveryFailure, Search } from "../types";

function makeSearch(overrides: Partial<Search> = {}): Search {
  return { ...sampleSearch, ...overrides };
}

function makeFailure(overrides: Partial<DeliveryFailure> = {}): DeliveryFailure {
  return {
    job_title: "Engineer",
    job_url: "https://example.test/job",
    error: "smtp timeout",
    sent_at: "2026-06-28T12:00:00Z",
    ...overrides,
  };
}

describe("SearchLastRun", () => {
  it("renders Never when there is no timestamp", () => {
    render(<SearchLastRun at={null} />);
    expect(screen.getByText("Never")).toBeInTheDocument();
  });

  it("renders a relative time with an absolute title", () => {
    render(<SearchLastRun at="2026-06-28T12:00:00Z" />);
    const el = screen.getByText(
      (_, node) => node instanceof HTMLElement && node.tagName === "SPAN" && node.title !== "",
    );
    expect(el).toHaveAttribute("title");
  });
});

describe("SearchHealthBadge", () => {
  it("shows a scrape error", () => {
    render(<SearchHealthBadge search={makeSearch({ last_error: "boom" })} />);
    expect(screen.getByText("scrape error")).toHaveClass("badge-health-error");
  });

  it("shows delivery issues", () => {
    render(
      <SearchHealthBadge
        search={makeSearch({ last_error: null, recent_delivery_failures: [makeFailure()] })}
      />,
    );
    expect(screen.getByText("delivery issues")).toHaveClass("badge-health-warn");
  });

  it("shows healthy when it has run without errors", () => {
    render(
      <SearchHealthBadge search={makeSearch({ last_error: null, recent_delivery_failures: [] })} />,
    );
    expect(screen.getByText("healthy")).toHaveClass("badge-health-ok");
  });

  it("shows not run yet when it never ran", () => {
    render(
      <SearchHealthBadge
        search={makeSearch({
          last_error: null,
          recent_delivery_failures: [],
          last_run_at: null,
        })}
      />,
    );
    expect(screen.getByText("not run yet")).toHaveClass("badge-health-unknown");
  });
});

describe("SearchHealthDetails", () => {
  it("renders nothing when healthy", () => {
    const { container } = render(
      <SearchHealthDetails
        search={makeSearch({ last_error: null, recent_delivery_failures: [] })}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the scrape error line", () => {
    render(
      <SearchHealthDetails
        search={makeSearch({ last_error: "connection refused", recent_delivery_failures: [] })}
      />,
    );
    expect(screen.getByText("connection refused")).toBeInTheDocument();
  });

  it("lists delivery failures including one without an error", () => {
    render(
      <SearchHealthDetails
        search={makeSearch({
          last_error: null,
          recent_delivery_failures: [
            makeFailure({ job_title: "Failing role", error: "smtp timeout" }),
            makeFailure({ job_title: "Silent role", error: null, sent_at: "2026-06-27T12:00:00Z" }),
          ],
        })}
      />,
    );
    expect(screen.getByText("Failing role")).toBeInTheDocument();
    expect(screen.getByText(/smtp timeout/)).toBeInTheDocument();
    expect(screen.getByText("Silent role")).toBeInTheDocument();
    expect(screen.getByText(/Delivery failures \(2\):/)).toBeInTheDocument();
  });

  it("marks five or more failures with a plus sign", () => {
    const failures = Array.from({ length: 5 }, (_, i) =>
      makeFailure({ job_title: `Role ${i}`, sent_at: `2026-06-2${i}T12:00:00Z` }),
    );
    render(
      <SearchHealthDetails
        search={makeSearch({ last_error: null, recent_delivery_failures: failures })}
      />,
    );
    expect(screen.getByText(/Delivery failures \(5\+\):/)).toBeInTheDocument();
  });

  it("renders a plain title when a failure job_url is a javascript: scheme", () => {
    render(
      <SearchHealthDetails
        search={makeSearch({
          last_error: null,
          recent_delivery_failures: [
            makeFailure({ job_title: "Hostile role", job_url: "javascript:alert(1)" }),
          ],
        })}
      />,
    );
    expect(screen.queryByRole("link", { name: "Hostile role" })).not.toBeInTheDocument();
    expect(screen.getByText(/Hostile role/)).toBeInTheDocument();
  });
});
