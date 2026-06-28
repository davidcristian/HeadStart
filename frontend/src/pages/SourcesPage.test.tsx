import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleSource } from "../test/fixtures";
import { SourcesPage } from "./SourcesPage";

describe("SourcesPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    render(<SourcesPage />);

    expect(screen.getByRole("heading", { name: "Sources" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("No sources yet.")).toBeInTheDocument());
  });

  it("lists existing sources", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    render(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    expect(screen.getByText("https://boards.greenhouse.io/acme")).toBeInTheDocument();
  });

  it("creates a source", async () => {
    render(<SourcesPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("ACME Careers"), {
      target: { value: "New Board" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create source" }));

    await waitFor(() => expect(mockApi.createSource).toHaveBeenCalled());
    expect(mockApi.createSource).toHaveBeenCalledWith(
      expect.objectContaining({ name: "New Board", adapter_key: "greenhouse" }),
    );
  });

  it("runs a test scrape and shows results", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    render(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() =>
      expect(screen.getByText(/Found 2 posting\(s\)/)).toBeInTheDocument(),
    );
  });

  it("deletes a source", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    render(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockApi.deleteSource).toHaveBeenCalledWith(sampleSource.id));
  });
});
