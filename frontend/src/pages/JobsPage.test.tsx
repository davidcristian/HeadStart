import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleJob, sampleSearch } from "../test/fixtures";
import { JobsPage } from "./JobsPage";

describe("JobsPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    render(<JobsPage />);

    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("No jobs seen yet. They appear here as searches run."),
      ).toBeInTheDocument(),
    );
  });

  it("lists discovered jobs", async () => {
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    render(<JobsPage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(screen.getByText("ACME")).toBeInTheDocument();
    expect(screen.getByText("Remote")).toBeInTheDocument();
    expect(screen.getByText("New", { selector: ".badge-job-new" })).toBeInTheDocument();
  });

  it("filters jobs by search", async () => {
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    render(<JobsPage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(mockApi.listJobs).toHaveBeenCalledWith(undefined, undefined);

    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[1], {
      target: { value: String(sampleSearch.id) },
    });

    await waitFor(() => expect(mockApi.listJobs).toHaveBeenCalledWith(sampleSearch.id, undefined));
  });

  it("filters jobs by status", async () => {
    mockApi.listJobs.mockResolvedValue([{ ...sampleJob, status: "applied" }]);
    render(<JobsPage />);

    await waitFor(() => expect(screen.getByText("Applied")).toBeInTheDocument());

    fireEvent.change(screen.getAllByRole("combobox")[0], {
      target: { value: "applied" },
    });

    await waitFor(() => expect(mockApi.listJobs).toHaveBeenCalledWith(undefined, "applied"));
  });

  it("updates job status from row actions", async () => {
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    render(<JobsPage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Applied" }));

    await waitFor(() =>
      expect(mockApi.updateJob).toHaveBeenCalledWith(sampleJob.id, { status: "applied" }),
    );
  });

  it("shows the RSS feed URL", async () => {
    render(<JobsPage />);

    await waitFor(() =>
      expect(
        screen.getByDisplayValue("http://localhost:8000/api/v1/feed/rss?token=test-token"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Copy feed URL" })).toBeInTheDocument();
  });
});
