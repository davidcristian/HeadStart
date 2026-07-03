import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import {
  sampleAccountPlan,
  sampleMeta,
  sampleSearch,
  sampleSource,
  sampleTarget,
} from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type { SearchRunResult } from "../types";
import { SearchesPage } from "./SearchesPage";

describe("SearchesPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty state", async () => {
    renderWithClient(<SearchesPage />);

    expect(screen.getByRole("heading", { name: "Searches" })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("No searches yet. Create one above.")).toBeInTheDocument(),
    );
  });

  it("lists existing searches with health info", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    expect(screen.getByText("healthy")).toBeInTheDocument();
    expect(screen.getByText("ACME Careers")).toBeInTheDocument();
  });

  it("creates a search", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<SearchesPage />);

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
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() => expect(screen.getByText(/Found 3, 1 new, 1 notified/)).toBeInTheDocument());
  });

  it("deletes a search", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(mockApi.deleteSearch).toHaveBeenCalledWith(sampleSearch.id));
  });

  it("toggles a disabled search on via the Enable button", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    mockApi.listSearches.mockResolvedValue([{ ...sampleSearch, enabled: false }]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Enable" }));

    await waitFor(() =>
      expect(mockApi.updateSearch).toHaveBeenCalledWith(sampleSearch.id, { enabled: true }),
    );
  });

  it("edits every form control, selects a target, and creates with them", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Google SWE Amsterdam"), {
      target: { value: "Full form" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: String(sampleSource.id) },
    });
    fireEvent.change(screen.getByLabelText("Notify via"), {
      target: { value: String(sampleTarget.id) },
    });
    fireEvent.change(screen.getByLabelText("Poll interval (seconds)"), {
      target: { value: "120" },
    });
    fireEvent.change(screen.getByPlaceholderText("https://..."), {
      target: { value: "https://jobs.example.test" },
    });
    // Switch to digest mode: reveals and edits the digest interval field.
    fireEvent.change(screen.getByLabelText("Notification mode"), {
      target: { value: "digest" },
    });
    const digestInput = document.querySelector(
      'input[type="number"][min="60"]',
    ) as HTMLInputElement;
    fireEvent.change(digestInput, { target: { value: "7200" } });
    // Edit the JSON config editor (valid JSON keeps the button enabled).
    const configEditor = document.querySelector("textarea.json-editor") as HTMLTextAreaElement;
    fireEvent.change(configEditor, { target: { value: '{"board_token":"acme"}' } });

    fireEvent.click(screen.getByRole("button", { name: "Create search" }));

    await waitFor(() =>
      expect(mockApi.createSearch).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Full form",
          source_id: sampleSource.id,
          target_id: sampleTarget.id,
          query_url: "https://jobs.example.test",
          interval_seconds: 120,
          notification_mode: "digest",
          digest_interval_seconds: 7200,
          config: { board_token: "acme" },
        }),
      ),
    );
  });

  it("disables the create button and shows the invalid-JSON hint when config is bad", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Google SWE Amsterdam"), {
      target: { value: "Name" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: String(sampleSource.id) },
    });
    const configEditor = document.querySelector("textarea.json-editor") as HTMLTextAreaElement;
    fireEvent.change(configEditor, { target: { value: "{not json" } });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create search" })).toBeDisabled(),
    );
  });

  it("resets the source selection back to none", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    const source = screen.getByLabelText("Source") as HTMLSelectElement;
    fireEvent.change(source, { target: { value: String(sampleSource.id) } });
    expect(source.value).toBe(String(sampleSource.id));
    fireEvent.change(source, { target: { value: "" } });
    expect(source.value).toBe("");
  });

  it("resets the notify target back to none", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listTargets.mockResolvedValue([sampleTarget]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    const target = screen.getByLabelText("Notify via") as HTMLSelectElement;
    fireEvent.change(target, { target: { value: String(sampleTarget.id) } });
    expect(target.value).toBe(String(sampleTarget.id));
    fireEvent.change(target, { target: { value: "" } });
    expect(target.value).toBe("");
  });

  it("surfaces a create failure as an error banner", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.createSearch.mockRejectedValueOnce(new Error("boom on create"));
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("Google SWE Amsterdam"), {
      target: { value: "Name" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: String(sampleSource.id) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create search" }));

    await waitFor(() => expect(screen.getByText("boom on create")).toBeInTheDocument());
  });

  it("shows a run-failed error banner when the run reports an error", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.runSearch.mockResolvedValueOnce({
      search_id: sampleSearch.id,
      found: 0,
      new: 0,
      notified: 0,
      failed: 0,
      skipped: 0,
      filtered: 0,
      queued: 0,
      closed: 0,
      error: "scraper exploded",
    } satisfies SearchRunResult as unknown as Awaited<ReturnType<typeof mockApi.runSearch>>);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() =>
      expect(screen.getByText("Run failed: scraper exploded")).toBeInTheDocument(),
    );
  });

  it("includes every optional count in the run notice", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.runSearch.mockResolvedValueOnce({
      search_id: sampleSearch.id,
      found: 10,
      new: 4,
      notified: 2,
      failed: 1,
      skipped: 1,
      filtered: 1,
      queued: 1,
      closed: 1,
      error: null,
    });
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          "Found 10, 4 new, 2 notified, 1 queued for digest, 1 filtered out, " +
            "1 skipped (already notified), 1 marked closed, 1 delivery failure(s).",
        ),
      ).toBeInTheDocument(),
    );
  });

  it("surfaces a thrown run error as an error banner", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.runSearch.mockRejectedValueOnce(new Error("network down"));
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Google SWE")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    await waitFor(() => expect(screen.getByText("network down")).toBeInTheDocument());
  });

  it("renders fallback ids and the '-' target when lookups miss and digest delivery text", async () => {
    mockApi.listSources.mockResolvedValue([]);
    mockApi.listTargets.mockResolvedValue([]);
    mockApi.listSearches.mockResolvedValue([
      {
        ...sampleSearch,
        id: 30,
        name: "Missing refs",
        source_id: 777,
        target_id: null,
        notification_mode: "digest",
        digest_interval_seconds: 1800,
      },
      {
        ...sampleSearch,
        id: 31,
        name: "Orphan target",
        source_id: sampleSource.id,
        target_id: 999,
      },
    ]);
    renderWithClient(<SearchesPage />);

    await waitFor(() => expect(screen.getByText("Missing refs")).toBeInTheDocument());
    expect(screen.getByText("#777")).toBeInTheDocument();
    expect(screen.getByText("-")).toBeInTheDocument();
    expect(screen.getByText("Digest every 1800s")).toBeInTheDocument();
    expect(screen.getByText("#999")).toBeInTheDocument();
  });

  it("shows the digest-restriction hint and Starter+ option on a plan without digest mode", async () => {
    mockApi.meta.mockResolvedValue({
      ...sampleMeta,
      plan: {
        ...sampleAccountPlan,
        plan: "free",
        effective_plan: "free",
        unlimited: false,
        limits: { max_searches: 3, max_sources: 3, max_targets: 1 },
        usage: { searches: 1, sources: 1, targets: 0 },
        features: { ...sampleAccountPlan.features, digest_mode: false },
      },
    });
    renderWithClient(
      <MemoryRouter>
        <SearchesPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByText("Digest mode requires Starter or above.")).toBeInTheDocument(),
    );
    expect(screen.getByText(/Digest \(batched summary\) — Starter\+/)).toBeInTheDocument();
    expect(screen.getByText(/1 \/ 3 searches used/)).toBeInTheDocument();
  });

  it("disables Create when the plan is at its search cap", async () => {
    mockApi.meta.mockResolvedValue({
      ...sampleMeta,
      plan: {
        ...sampleAccountPlan,
        plan: "free",
        effective_plan: "free",
        unlimited: false,
        limits: { max_searches: 3, max_sources: 3, max_targets: 1 },
        usage: { searches: 3, sources: 1, targets: 0 },
      },
    });
    mockApi.listSources.mockResolvedValue([sampleSource]);
    renderWithClient(
      <MemoryRouter>
        <SearchesPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("ACME Careers (greenhouse)")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("Google SWE Amsterdam"), {
      target: { value: "Name" },
    });
    fireEvent.change(screen.getByLabelText("Source"), {
      target: { value: String(sampleSource.id) },
    });

    expect(screen.getByRole("button", { name: "Create search" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "View plans" })).toBeInTheDocument();
  });
});
