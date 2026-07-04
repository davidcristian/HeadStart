import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleMeta, sampleSource } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type { SourceTestResult } from "../types";
import { SourcesPage } from "./SourcesPage";

describe("SourcesPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    renderWithClient(<SourcesPage />);

    expect(screen.getByRole("heading", { name: "Sources" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("No sources yet.")).toBeInTheDocument());
  });

  it("lists existing sources", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    expect(screen.getByText("https://boards.greenhouse.io/acme")).toBeInTheDocument();
  });

  it("creates a source", async () => {
    renderWithClient(<SourcesPage />);
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

  it("adds a curated portal as a source", async () => {
    renderWithClient(<SourcesPage />);
    await waitFor(() => expect(screen.getByText("Stripe")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Add source" }));

    await waitFor(() => expect(mockApi.createSource).toHaveBeenCalled());
    expect(mockApi.createSource).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Stripe",
        adapter_key: "greenhouse",
        base_url: "https://boards.greenhouse.io/stripe",
      }),
    );
  });

  it("runs a test scrape and shows results", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() => expect(screen.getByText(/Found 2 posting\(s\)/)).toBeInTheDocument());
  });

  it("deletes a source", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockApi.deleteSource).toHaveBeenCalledWith(sampleSource.id));
  });

  it("toggles auto-apply opt-in", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() =>
      expect(mockApi.updateSource).toHaveBeenCalledWith(sampleSource.id, {
        auto_apply_enabled: true,
      }),
    );
  });

  it("edits the adapter, base URL, and config fields before creating", async () => {
    renderWithClient(<SourcesPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("ACME Careers"), {
      target: { value: "Custom Board" },
    });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "lever" } });
    fireEvent.change(screen.getByPlaceholderText("https://..."), {
      target: { value: "https://jobs.example.com" },
    });
    const jsonEditor = screen
      .getAllByRole("textbox")
      .find((el) => el.className.includes("json-editor"))!;
    fireEvent.change(jsonEditor, { target: { value: '{"site":"custom"}' } });

    fireEvent.click(screen.getByRole("button", { name: "Create source" }));

    await waitFor(() => expect(mockApi.createSource).toHaveBeenCalled());
    expect(mockApi.createSource).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Custom Board",
        adapter_key: "lever",
        base_url: "https://jobs.example.com",
        default_config: { site: "custom" },
      }),
    );
  });

  it("disables Create when the config JSON is invalid", async () => {
    renderWithClient(<SourcesPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("ACME Careers"), {
      target: { value: "Broken" },
    });
    const jsonEditor = screen
      .getAllByRole("textbox")
      .find((el) => el.className.includes("json-editor"))!;
    fireEvent.change(jsonEditor, { target: { value: "{not valid" } });

    expect(screen.getByRole("button", { name: "Create source" })).toBeDisabled();
  });

  it("surfaces an error banner when creating a source fails", async () => {
    mockApi.createSource.mockRejectedValueOnce(new Error("boom"));
    renderWithClient(<SourcesPage />);
    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());

    fireEvent.change(screen.getByPlaceholderText("ACME Careers"), {
      target: { value: "New Board" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create source" }));

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());
  });

  it("toggles a source enabled state", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    // sampleSource is enabled -> the button reads "Disable".
    fireEvent.click(screen.getByRole("button", { name: "Disable" }));

    await waitFor(() =>
      expect(mockApi.updateSource).toHaveBeenCalledWith(sampleSource.id, { enabled: false }),
    );
  });

  it("shows an Enable button and N/A auto-apply for disabled non-applier sources", async () => {
    mockApi.listSources.mockResolvedValue([
      {
        ...sampleSource,
        enabled: false,
        adapter_key: "generic_html",
      },
    ]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    expect(screen.getByText("N/A")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));

    await waitFor(() =>
      expect(mockApi.updateSource).toHaveBeenCalledWith(sampleSource.id, { enabled: true }),
    );
  });

  it("shows the Enabled label for a source with auto-apply on", async () => {
    mockApi.listSources.mockResolvedValue([{ ...sampleSource, auto_apply_enabled: true }]);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("reports a failed test scrape via the error banner", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.testSource.mockResolvedValueOnce({
      ok: false,
      found: 0,
      sample: [],
      error: "scrape exploded",
    } satisfies SourceTestResult as unknown as Awaited<ReturnType<typeof mockApi.testSource>>);
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() => expect(screen.getByText("scrape exploded")).toBeInTheDocument());
  });

  it("falls back to a default message when a failed test has no error", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.testSource.mockResolvedValueOnce({
      ok: false,
      found: 0,
      sample: [],
      error: null,
    });
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() => expect(screen.getByText("Source test failed")).toBeInTheDocument());
  });

  it("omits the sample preview when postings have no titles", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.testSource.mockResolvedValueOnce({
      ok: true,
      found: 1,
      sample: [{ external_id: "1", title: "", company: "ACME", location: "", url: "" }],
      error: null,
    });
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() => expect(screen.getByText("Found 1 posting(s).")).toBeInTheDocument());
  });

  it("surfaces an error banner when the test scrape throws", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.testSource.mockRejectedValueOnce(new Error("network down"));
    renderWithClient(<SourcesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Test scrape" }));

    await waitFor(() => expect(screen.getByText("network down")).toBeInTheDocument());
  });

  it("disables Create when the plan is at its source cap", async () => {
    mockApi.meta.mockResolvedValue({
      ...sampleMeta,
      plan: {
        ...sampleMeta.plan,
        unlimited: false,
        limits: { max_searches: 50, max_sources: 1, max_targets: 20, max_auto_applies_per_day: 50 },
        usage: { searches: 0, sources: 1, targets: 0, auto_applies_last_day: 0 },
      },
    });
    renderWithClient(
      <MemoryRouter>
        <SourcesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(mockApi.meta).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText("ACME Careers"), {
      target: { value: "Capped" },
    });

    // The manual-create button lives in the "Add a source manually" card.
    const card = screen.getByText("Add a source manually").closest(".card") as HTMLElement;
    expect(within(card).getByRole("button", { name: "Create source" })).toBeDisabled();
  });
});
