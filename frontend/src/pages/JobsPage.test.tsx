import { mockApi, resetMockApi } from "../test/mockApi";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { sampleJob, sampleMeta, sampleProfile, sampleSearch, sampleSource } from "../test/fixtures";
import { sampleFeedUrl, sampleRotatedFeedUrl } from "../test/mockApiSamples";
import { renderWithClient } from "../test/renderWithClient";
import { JobsPage } from "./JobsPage";

function renderJobsPage() {
  return renderWithClient(
    <MemoryRouter>
      <JobsPage />
    </MemoryRouter>,
  );
}

/** Dispatch a synthetic touch event with a controllable clientY. */
function dispatchTouch(type: "touchstart" | "touchmove" | "touchend", clientY?: number) {
  const event = new Event(type) as unknown as {
    type: string;
    touches: Array<{ clientY: number }>;
  };
  event.touches = clientY === undefined ? [] : [{ clientY }];
  act(() => {
    window.dispatchEvent(event as unknown as Event);
  });
}

/** Free-plan meta with RSS export disabled. */
const freePlanMeta = {
  ...sampleMeta,
  plan: {
    ...sampleMeta.plan,
    plan: "free" as const,
    features: { ...sampleMeta.plan.features, rss_feed: false },
  },
};

describe("JobsPage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  afterEach(() => {
    // Reset the feed mocks that resetMockApi does not cover so overrides in one
    // test (rejections / hanging promises) do not leak into the next.
    mockApi.getFeedUrl.mockResolvedValue(sampleFeedUrl);
    mockApi.rotateFeedUrl.mockResolvedValue(sampleRotatedFeedUrl);
  });

  it("renders the page and empty state", async () => {
    renderJobsPage();

    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("No jobs seen yet. They appear here as searches run."),
      ).toBeInTheDocument(),
    );
  });

  it("lists discovered jobs", async () => {
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(screen.getByText("ACME")).toBeInTheDocument();
    expect(screen.getByText("Remote")).toBeInTheDocument();
    expect(screen.getByText("$150K – $180K")).toBeInTheDocument();
    expect(screen.getByText("New", { selector: ".badge-job-new" })).toBeInTheDocument();
  });

  it("filters jobs by search", async () => {
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

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
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Applied")).toBeInTheDocument());

    fireEvent.change(screen.getAllByRole("combobox")[0], {
      target: { value: "applied" },
    });

    await waitFor(() => expect(mockApi.listJobs).toHaveBeenCalledWith(undefined, "applied"));
  });

  it("updates job status from row actions", async () => {
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Applied" }));

    await waitFor(() =>
      expect(mockApi.updateJob).toHaveBeenCalledWith(sampleJob.id, { status: "applied" }),
    );
  });

  it("shows the RSS feed URL", async () => {
    renderJobsPage();

    await waitFor(() =>
      expect(
        screen.getByDisplayValue("http://localhost:8000/api/v1/feed/rss?token=test-token"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Copy feed URL" })).toBeInTheDocument();
  });

  it("opens the apply dialog for supported jobs", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Apply to Software Engineer" })).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Dear ACME team/)).toBeInTheDocument();
  });

  it("previews an application from the dialog", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderJobsPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() =>
      expect(mockApi.applyToJob).toHaveBeenCalledWith(sampleJob.id, {
        dry_run: true,
        cover_letter: "Dear ACME team, ...",
        tailored_resume_b64: null,
        tailored_resume_artifact_id: null,
      }),
    );
    expect(screen.getByText("Application preview")).toBeInTheDocument();
  });

  it("generates a cover letter from the apply dialog", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderJobsPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));

    await waitFor(() => expect(mockApi.generateCoverLetter).toHaveBeenCalledWith(sampleJob.id));
    expect(
      screen.getByDisplayValue(/I am excited about the Software Engineer role/),
    ).toBeInTheDocument();
  });

  it("closes the apply dialog and uses defaults when profile has no template", async () => {
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    // Default profile from resetMockApi has exists=false and an empty template,
    // exercising the empty cover-letter and profileReady=false branches.
    renderJobsPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("renders jobs while searches and sources data have not loaded yet", async () => {
    // Force the searches/sources queries to hang so their `.data` stays
    // undefined, exercising the `?? []` fallbacks inside jobCanApply. The Apply
    // button will not appear (no source found) but the callback still runs.
    mockApi.listSearches.mockImplementation(() => new Promise(() => {}));
    mockApi.listSources.mockImplementation(() => new Promise(() => {}));
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });

  it("treats a source without an auto-apply flag as not auto-applying", async () => {
    // adapter_key is in appliers so Apply is clickable, but auto_apply_enabled
    // is undefined, exercising the `?? false` fallback in applyAutoApplyEnabled.
    const sourceNoFlag = {
      ...sampleSource,
      auto_apply_enabled: undefined as unknown as boolean,
    };
    mockApi.listSources.mockResolvedValue([sourceNoFlag]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderJobsPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("opens apply with an unloaded profile using safe defaults", async () => {
    // The profile query hangs so profile.data stays undefined, exercising the
    // `?? ""` cover-letter fallback and the `?? false` profileReady fallback.
    mockApi.listSources.mockResolvedValue([sampleSource]);
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    mockApi.getProfile.mockImplementation(() => new Promise(() => {}));
    renderJobsPage();

    await waitFor(() => expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("copies the filtered feed URL and selects the input on focus", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
      writable: true,
    });
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    const input = (await screen.findByDisplayValue(
      "http://localhost:8000/api/v1/feed/rss?token=test-token",
    )) as HTMLInputElement;
    const selectSpy = vi.spyOn(input, "select");
    fireEvent.focus(input);
    expect(selectSpy).toHaveBeenCalled();

    // Apply both filters so the copied URL includes the query params.
    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "new" } });
    fireEvent.change(screen.getAllByRole("combobox")[1], {
      target: { value: String(sampleSearch.id) },
    });

    fireEvent.click(screen.getByRole("button", { name: "Copy feed URL" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`search_id=${sampleSearch.id}`));
    expect(writeText.mock.calls[0][0]).toContain("status=new");
    await waitFor(() =>
      expect(screen.getByText("RSS feed URL copied to clipboard.")).toBeInTheDocument(),
    );
  });

  it("regenerates the feed link", async () => {
    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Regenerate link" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Regenerate link" }));

    await waitFor(() => expect(mockApi.rotateFeedUrl).toHaveBeenCalledTimes(1));
    expect(
      await screen.findByText(
        "RSS feed link regenerated. Update any feed readers using the old URL.",
      ),
    ).toBeInTheDocument();
  });

  it("clears the search filter back to all searches", async () => {
    mockApi.listSearches.mockResolvedValue([sampleSearch]);
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    const searchSelect = screen.getAllByRole("combobox")[1];

    fireEvent.change(searchSelect, { target: { value: String(sampleSearch.id) } });
    await waitFor(() => expect(mockApi.listJobs).toHaveBeenCalledWith(sampleSearch.id, undefined));

    fireEvent.change(searchSelect, { target: { value: "" } });
    await waitFor(() => expect(mockApi.listJobs).toHaveBeenLastCalledWith(undefined, undefined));
  });

  it("shows the upgrade hint when RSS export is not on the plan", async () => {
    mockApi.meta.mockResolvedValue(freePlanMeta);
    renderJobsPage();

    expect(await screen.findByText(/RSS export is available on the Pro plan/)).toBeInTheDocument();
    expect(screen.getByText("Free", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Compare plans" })).toHaveAttribute("href", "/pricing");
    // RSS feed URL controls are not rendered on the free plan.
    expect(screen.queryByRole("button", { name: "Copy feed URL" })).not.toBeInTheDocument();
  });

  it("shows an error banner when the feed URL fails to load", async () => {
    mockApi.getFeedUrl.mockRejectedValue(new Error("boom"));
    renderJobsPage();

    expect(await screen.findByText("Could not load RSS feed URL.")).toBeInTheDocument();
  });

  it("shows a loading state while the feed URL is pending", async () => {
    mockApi.getFeedUrl.mockImplementation(() => new Promise(() => {}));
    renderJobsPage();

    expect(await screen.findByText("Loading feed URL...")).toBeInTheDocument();
  });

  it("shows the pull-to-refresh indicator and refetches jobs on pull", async () => {
    mockApi.listJobs.mockResolvedValue([sampleJob]);
    renderJobsPage();

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    const callsBefore = mockApi.listJobs.mock.calls.length;

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 200); // delta >= 72 -> ready
    expect(screen.getByText("Release to refresh")).toBeInTheDocument();

    await act(async () => {
      dispatchTouch("touchend");
      await Promise.resolve();
    });

    // The pull triggered a refetch of the jobs list.
    await waitFor(() => expect(mockApi.listJobs.mock.calls.length).toBeGreaterThan(callsBefore));
    // The transient refreshing indicator clears once the refresh settles.
    await waitFor(() => expect(screen.queryByText("Release to refresh")).not.toBeInTheDocument());
  });

  it("renders the refreshing indicator during an in-flight pull refresh", async () => {
    // Make the jobs refetch hang so the `refreshing` state (and thus the
    // "Refreshing jobs..." branch) is committed and observable.
    mockApi.listJobs.mockResolvedValueOnce([sampleJob]);
    renderJobsPage();
    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());

    let resolveRefetch: (value: (typeof sampleJob)[]) => void = () => {};
    mockApi.listJobs.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRefetch = resolve;
        }),
    );

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 200);

    await act(async () => {
      dispatchTouch("touchend");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("Refreshing jobs...")).toBeInTheDocument();

    await act(async () => {
      resolveRefetch([sampleJob]);
      await Promise.resolve();
    });
    await waitFor(() => expect(screen.queryByText("Refreshing jobs...")).not.toBeInTheDocument());
  });

  it("shows a loading state while jobs are pending", async () => {
    mockApi.listJobs.mockImplementation(() => new Promise(() => {}));
    renderJobsPage();

    expect(await screen.findByText("Loading...")).toBeInTheDocument();
  });
});
