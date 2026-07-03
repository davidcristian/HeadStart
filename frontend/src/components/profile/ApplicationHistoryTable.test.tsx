import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApplicationLog } from "../../types";
import { ApplicationHistoryTable } from "./ApplicationHistoryTable";

function makeEntry(overrides: Partial<ApplicationLog> = {}): ApplicationLog {
  return {
    id: 1,
    seen_job_id: 100,
    job_title: "Software Engineer",
    job_company: "ACME",
    job_url: "https://example.test/jobs/1",
    status: "submitted",
    dry_run: false,
    error: null,
    payload: null,
    external_application_id: "gh-123",
    tailored_resume_artifact: null,
    created_at: "2026-06-28T12:00:00Z",
    ...overrides,
  };
}

describe("ApplicationHistoryTable", () => {
  it("shows a loading state while pending", () => {
    render(<ApplicationHistoryTable entries={undefined} isPending={true} />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows the empty state when entries are undefined", () => {
    render(<ApplicationHistoryTable entries={undefined} isPending={false} />);

    expect(screen.getByText("No application attempts yet.")).toBeInTheDocument();
  });

  it("shows the empty state when entries is an empty array", () => {
    render(<ApplicationHistoryTable entries={[]} isPending={false} />);

    expect(screen.getByText("No application attempts yet.")).toBeInTheDocument();
  });

  it("renders a submitted row with id and posting link", () => {
    render(<ApplicationHistoryTable entries={[makeEntry()]} isPending={false} />);

    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("ACME")).toBeInTheDocument();
    expect(screen.getByText("submitted")).toBeInTheDocument();
    expect(screen.getByText("ID: gh-123")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View posting" })).toHaveAttribute(
      "href",
      "https://example.test/jobs/1",
    );
  });

  it("labels a dry run as a preview and shows the error", () => {
    render(
      <ApplicationHistoryTable
        entries={[makeEntry({ dry_run: true, error: "boom" })]}
        isPending={false}
      />,
    );

    expect(screen.getByText("Preview")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("omits the id line and posting link when both are absent", () => {
    render(
      <ApplicationHistoryTable
        entries={[makeEntry({ external_application_id: null, job_url: "" })]}
        isPending={false}
      />,
    );

    expect(screen.queryByText(/^ID:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View posting" })).not.toBeInTheDocument();
  });
});
