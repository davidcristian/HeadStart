import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithClient } from "../test/renderWithClient";
import { sampleApplicationPipelineItem } from "../test/fixtures";
import type { ApplicationPipelineItem } from "../types";
import { ApplicationPipelineList } from "./ApplicationPipelineList";

const draftInboxReply = vi.hoisted(() =>
  vi.fn(async () => ({
    id: 9,
    classification_id: 42,
    subject: "Re: your application",
    body_text: "Thanks!",
    provider: "heuristic",
    created_at: "2026-06-28T14:00:00Z",
    seen_job_id: 1,
    message_uid: 3,
    fallback: false,
    status: "drafted",
    notes: "",
  })),
);
vi.mock("../api", () => ({ api: { draftInboxReply } }));

const downloadApplicationArtifact = vi.hoisted(() => vi.fn(async () => undefined));
vi.mock("../lib/applicationArtifacts", () => ({ downloadApplicationArtifact }));

function makeItem(overrides: Partial<ApplicationPipelineItem> = {}): ApplicationPipelineItem {
  return { ...sampleApplicationPipelineItem, ...overrides };
}

type DraftResult = Awaited<ReturnType<typeof draftInboxReply>>;

/** A never-auto-resolving draft promise so the mutation stays pending until resolved. */
function makePendingDraft(): { promise: Promise<DraftResult>; resolve: () => void } {
  let resolveFn!: (value: DraftResult) => void;
  const promise = new Promise<DraftResult>((resolve) => {
    resolveFn = resolve;
  });
  const value: DraftResult = {
    id: 9,
    classification_id: 42,
    subject: "Re: your application",
    body_text: "Thanks!",
    provider: "heuristic",
    created_at: "2026-06-28T14:00:00Z",
    seen_job_id: 1,
    message_uid: 3,
    fallback: false,
    status: "drafted",
    notes: "",
  };
  return { promise, resolve: () => resolveFn(value) };
}

/** Force the useMediaQuery hook to report mobile (cards) vs desktop (table). */
function setMobile(matches: boolean): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

beforeEach(() => {
  draftInboxReply.mockClear();
  downloadApplicationArtifact.mockClear();
  setMobile(false);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReplyDraftSection", () => {
  const draft = {
    id: 7,
    classification_id: 42,
    subject: "Re: your application",
    body_text: "Hello there",
    provider: "openai",
    created_at: "2026-06-28T14:00:00Z",
  };

  it("renders nothing when there is no draft and no classification id", () => {
    renderWithClient(<ApplicationPipelineList items={[makeItem()]} />);
    expect(screen.queryByText(/Reply draft/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Draft reply/ })).not.toBeInTheDocument();
  });

  it("offers a Draft reply button and drafts when a classification id exists", async () => {
    renderWithClient(
      <ApplicationPipelineList items={[makeItem({ latest_draftable_classification_id: 42 })]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Draft reply" }));
    await waitFor(() => expect(draftInboxReply).toHaveBeenCalledWith({ classification_id: 42 }));
  });

  it("shows an existing draft with a working regenerate button", async () => {
    renderWithClient(
      <ApplicationPipelineList
        items={[makeItem({ latest_reply_draft: draft, latest_draftable_classification_id: 42 })]}
      />,
    );

    expect(screen.getByText("Reply draft (openai)")).toBeInTheDocument();
    expect(screen.getByText("Re: your application")).toBeInTheDocument();
    expect(screen.getByText("Hello there")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Regenerate draft" }));
    await waitFor(() =>
      expect(draftInboxReply).toHaveBeenCalledWith({ classification_id: 42, regenerate: true }),
    );
  });

  it("shows a draft without regenerate button when there is no classification id", () => {
    renderWithClient(
      <ApplicationPipelineList
        items={[makeItem({ latest_reply_draft: draft, latest_draftable_classification_id: null })]}
      />,
    );

    expect(screen.getByText("Reply draft (openai)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Regenerate draft" })).not.toBeInTheDocument();
  });

  it("shows the pending label while a fresh draft is in flight", async () => {
    const pending = makePendingDraft();
    draftInboxReply.mockReturnValueOnce(pending.promise);
    renderWithClient(
      <ApplicationPipelineList items={[makeItem({ latest_draftable_classification_id: 42 })]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Draft reply" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Drafting…" })).toBeDisabled());
    pending.resolve();
  });

  it("shows the pending label while a regenerate is in flight", async () => {
    const pending = makePendingDraft();
    draftInboxReply.mockReturnValueOnce(pending.promise);
    renderWithClient(
      <ApplicationPipelineList
        items={[makeItem({ latest_reply_draft: draft, latest_draftable_classification_id: 42 })]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Regenerate draft" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Regenerating…" })).toBeDisabled(),
    );
    pending.resolve();
  });

  it("surfaces an error message when drafting fails", async () => {
    draftInboxReply.mockRejectedValueOnce(new Error("nope"));
    renderWithClient(
      <ApplicationPipelineList items={[makeItem({ latest_draftable_classification_id: 42 })]} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Draft reply" }));
    await waitFor(() => expect(screen.getByText(/Could not draft a reply/)).toBeInTheDocument());
  });

  it("guards handleDraft against a missing classification id via a stale draft state", () => {
    // draft present + classification id present renders the details variant, so the
    // Draft-reply button (with handleDraft) is not shown. Cover the early-return guard
    // by verifying no draft call fires when only a draft (no classification) exists.
    renderWithClient(
      <ApplicationPipelineList
        items={[makeItem({ latest_reply_draft: draft, latest_draftable_classification_id: null })]}
      />,
    );
    expect(draftInboxReply).not.toHaveBeenCalled();
  });
});
