import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { sampleJob } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type {
  DocumentGeneration,
  JobApplyResult,
  JobCoverLetterResult,
  JobResumeResult,
} from "../types";
import { ApplyJobDialog } from "./ApplyJobDialog";

// The shared mockApi infers narrow return types from its default fixtures; re-type
// the handles this suite drives with the real API result types so mockResolvedValue
// accepts the richer response shapes these tests exercise.
const applyToJobMock = mockApi.applyToJob as unknown as Mock<
  (id: number, data: unknown) => Promise<JobApplyResult>
>;
const generateCoverLetterMock = mockApi.generateCoverLetter as unknown as Mock<
  () => Promise<DocumentGeneration>
>;
const generateResumeMock = mockApi.generateResume as unknown as Mock<
  () => Promise<DocumentGeneration>
>;

const pollApplicationLog = vi.hoisted(() => vi.fn());
const pollDocumentGeneration = vi.hoisted(() => vi.fn());
const previewApplicationArtifact = vi.hoisted(() => vi.fn());

vi.mock("../api/pollApplicationLog", () => ({
  pollApplicationLog: (id: number) => pollApplicationLog(id),
}));
vi.mock("../api/pollDocumentGeneration", () => ({
  pollDocumentGeneration: (id: number) => pollDocumentGeneration(id),
}));
vi.mock("../lib/applicationArtifacts", () => ({
  previewApplicationArtifact: (id: number) => previewApplicationArtifact(id),
}));

function queuedGeneration(
  kind: DocumentGeneration["kind"],
  id = kind === "resume" ? 2 : 1,
): DocumentGeneration {
  return {
    id,
    kind,
    status: "queued",
    error: null,
    result: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

function readyCover(result: JobCoverLetterResult): DocumentGeneration {
  return {
    id: 1,
    kind: "cover_letter",
    status: "ready",
    error: null,
    result,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

function readyResume(result: JobResumeResult): DocumentGeneration {
  return {
    id: 2,
    kind: "resume",
    status: "ready",
    error: null,
    result,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

function renderDialog(props: Partial<Parameters<typeof ApplyJobDialog>[0]> = {}) {
  const onClose = props.onClose ?? vi.fn();
  const utils = renderWithClient(
    <MemoryRouter>
      <ApplyJobDialog
        job={sampleJob}
        open
        initialCoverLetter="Initial letter"
        profileReady
        autoApplyEnabled
        onClose={onClose}
        {...props}
      />
    </MemoryRouter>,
  );
  return { ...utils, onClose };
}

function textarea(): HTMLTextAreaElement {
  return screen.getByRole("textbox") as HTMLTextAreaElement;
}

describe("ApplyJobDialog busy and disabled states", () => {
  beforeEach(() => {
    resetMockApi();
    pollApplicationLog.mockReset();
    pollDocumentGeneration.mockReset();
    previewApplicationArtifact.mockReset();
    applyToJobMock.mockResolvedValue({
      status: "dry_run",
      error: null,
      payload: { email: "ada@example.com" },
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    generateCoverLetterMock.mockResolvedValue(queuedGeneration("cover_letter"));
    generateResumeMock.mockResolvedValue(queuedGeneration("resume"));
    pollDocumentGeneration.mockImplementation(async (id: number) => {
      if (id === 2) {
        return readyResume({
          filename: "resume.pdf",
          size_bytes: 1234,
          content_sha256: "abc",
          pdf_b64: "JVBERi0=",
          artifact_id: 55,
          provider: "heuristic",
          fallback: false,
        });
      }
      return readyCover({
        cover_letter: "Generated letter",
        provider: "heuristic",
        fallback: false,
      });
    });
  });

  it("shows busy labels while an apply is in flight", async () => {
    let resolveApply: (v: JobApplyResult) => void = () => {};
    applyToJobMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApply = resolve;
        }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Previewing..." })).toBeInTheDocument(),
    );
    resolveApply({
      status: "dry_run",
      error: null,
      payload: { a: 1 },
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument(),
    );
  });

  it("shows the submitting label and disables submit while a live apply is in flight", async () => {
    let resolveApply: (v: JobApplyResult) => void = () => {};
    applyToJobMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveApply = resolve;
        }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Submitting..." })).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Submitting..." })).toBeDisabled();
    resolveApply({
      status: "submitted",
      error: null,
      payload: null,
      external_application_id: "x",
      job: null,
      application_log_id: null,
    });
    await waitFor(() =>
      expect(
        screen.getByText("Application submitted for Software Engineer at ACME."),
      ).toBeInTheDocument(),
    );
  });

  it("shows generating labels and disables actions while a cover letter is generating", async () => {
    let resolveGen: (v: DocumentGeneration) => void = () => {};
    generateCoverLetterMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve;
        }),
    );
    pollDocumentGeneration.mockResolvedValue(
      readyCover({ cover_letter: "done", provider: "heuristic", fallback: false }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Generating..." })).toBeInTheDocument(),
    );
    expect(textarea()).toBeDisabled();
    resolveGen(queuedGeneration("cover_letter"));
    await waitFor(() => expect(textarea().value).toBe("done"));
  });

  it("shows the generating label on the resume button while a resume is generating", async () => {
    let resolveGen: (v: DocumentGeneration) => void = () => {};
    generateResumeMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve;
        }),
    );
    pollDocumentGeneration.mockResolvedValue(
      readyResume({
        filename: "resume.pdf",
        size_bytes: 5,
        content_sha256: "y",
        pdf_b64: "JVBERi0=",
        artifact_id: 3,
        provider: "heuristic",
        fallback: false,
      }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Generating..." })).toBeInTheDocument(),
    );
    // The cover letter button keeps its label; only the resume button is busy.
    expect(screen.getByRole("button", { name: "Generate cover letter" })).toBeDisabled();
    resolveGen(queuedGeneration("resume"));
    await waitFor(() => expect(screen.getByText(/Tailored resume ready:/)).toBeInTheDocument());
  });

  it("disables the generate buttons when the profile is not ready", () => {
    renderDialog({ profileReady: false });
    expect(screen.getByRole("button", { name: "Generate cover letter" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Generate tailored resume" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Preview" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Submit application" })).toBeDisabled();
  });

  it("hides the Preview PDF button when the resume has no artifact id", async () => {
    pollDocumentGeneration.mockResolvedValue(
      readyResume({
        filename: "resume.pdf",
        size_bytes: 10,
        content_sha256: "x",
        pdf_b64: "JVBERi0=",
        // artifact_id null exercises the tailoredResumeArtifactId === null branch.
        artifact_id: null as unknown as number,
        provider: "heuristic",
        fallback: false,
      }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() => expect(screen.getByText(/Tailored resume ready:/)).toBeInTheDocument());
    const meta = screen.getByText(/Tailored resume ready:/).closest(".apply-tailored-resume-meta")!;
    expect(within(meta as HTMLElement).queryByRole("button", { name: "Preview PDF" })).toBeNull();

    // Because there is no artifact id, the apply payload should send the raw b64.
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(mockApi.applyToJob).toHaveBeenCalled());
    expect(mockApi.applyToJob).toHaveBeenCalledWith(sampleJob.id, {
      dry_run: true,
      cover_letter: "Initial letter",
      tailored_resume_b64: "JVBERi0=",
      tailored_resume_artifact_id: null,
    });
  });
});
