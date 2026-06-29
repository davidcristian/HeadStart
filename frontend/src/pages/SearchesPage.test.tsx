import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleSearch, sampleSource, sampleTarget } from "../test/fixtures";
import { SearchesPage } from "./SearchesPage";

describe("SearchesPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    render(<SearchesPage />);

    expect(screen.getByRole("heading", { name: "Searches" })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("No searches yet. Create one above.")).toBeInTheDocument(),
    );
  });

  it("lists existing searches with health info", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    render(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(screen.getByText("ACME Careers")).toBeInTheDocument();
  });

  it("creates a search", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    render(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Google SWE Amsterdam"), {
      target: { value: "Backend roles" },
    });
    fireEvent.change(screen.getByPlaceholderText("engineer backend"), {
      target: { value: "backend" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: String(sampleSource.id) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create search" }));

    await waitFor(() => expect(mockApi.createSearch).toHaveBeenCalled());
    expect(mockApi.createSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Backend roles",
        source_id: sampleSource.id,
        filters: { keywords: "backend" },
      }),
    );
  });

  it("runs a search immediately and shows results", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    render(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() => expect(screen.getByText(/Found 3, 1 new, 1 notified/)).toBeInTheDocument());
  });

  it("deletes a search", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    render(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockApi.deleteSearch).toHaveBeenCalledWith(sampleSearch.id));
  });
});
