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
  });

  it("filters jobs by search", async () => {
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    render(<JobsPage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(mockApi.listJobs).toHaveBeenCalledWith(undefined);

    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: String(sampleSearch.id) },
    });

    await waitFor(() => expect(mockApi.listJobs).toHaveBeenCalledWith(sampleSearch.id));
  });
});
