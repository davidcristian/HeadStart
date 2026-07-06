import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { sampleJob } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type {
  ApplicationLog,
  DocumentGeneration,
  Job,
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

function terminalLog(overrides: Partial<ApplicationLog> = {}): ApplicationLog {
  return {
    id: 1,
    seen_job_id: sampleJob.id,
    job_title: sampleJob.title,
    job_company: sampleJob.company,
    job_url: sampleJob.url,
    status: "submitted",
    dry_run: false,
    error: null,
    payload: null,
    external_application_id: "app-1",
    tailored_resume_artifact: null,
    created_at: "2026-06-28T12:00:00Z",
    ...overrides,
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

describe("ApplyJobDialog apply flow", () => {
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

  it("previews the payload on a dry-run apply", async () => {
    applyToJobMock.mockResolvedValue({
      status: "dry_run",
      error: null,
      payload: { email: "ada@example.com", note: "hi" },
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(screen.getByText("Application preview")).toBeInTheDocument());
    expect(screen.getByText(/"email": "ada@example.com"/)).toBeInTheDocument();
  });

  it("sends the trimmed cover letter (or null) and the raw resume base64 when no artifact id", async () => {
    // No resume generated -> tailoredResumeArtifactId is null, so b64 branch would
    // send null; blank cover letter -> null. Verify the apply payload shape.
    renderDialog({ initialCoverLetter: "   " });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(mockApi.applyToJob).toHaveBeenCalled());
    expect(mockApi.applyToJob).toHaveBeenCalledWith(sampleJob.id, {
      dry_run: true,
      cover_letter: null,
      tailored_resume_b64: null,
      tailored_resume_artifact_id: null,
    });
  });

  it("submits and reaches success when the apply is immediately submitted", async () => {
    applyToJobMock.mockResolvedValue({
      status: "submitted",
      error: null,
      payload: null,
      external_application_id: "ext-1",
      job: null,
      application_log_id: null,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      expect(
        screen.getByText("Application submitted for Software Engineer at ACME."),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
  });

  it("polls a queued application to success", async () => {
    applyToJobMock.mockResolvedValue({
      status: "queued",
      error: null,
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: 99,
    });
    pollApplicationLog.mockResolvedValue(terminalLog({ status: "submitted" }));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      expect(
        screen.getByText("Application submitted for Software Engineer at ACME."),
      ).toBeInTheDocument(),
    );
    expect(pollApplicationLog).toHaveBeenCalledWith(99);
  });

  it("shows the poll error when the queued application fails", async () => {
    applyToJobMock.mockResolvedValue({
      status: "queued",
      error: null,
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: 99,
    });
    pollApplicationLog.mockResolvedValue(terminalLog({ status: "failed", error: "poll failed" }));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() => expect(screen.getByText("poll failed")).toBeInTheDocument());
  });

  it("shows a default error when the queued application fails without a message", async () => {
    applyToJobMock.mockResolvedValue({
      status: "queued",
      error: null,
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: 99,
    });
    pollApplicationLog.mockResolvedValue(terminalLog({ status: "failed", error: null }));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() => expect(screen.getByText("Application failed.")).toBeInTheDocument());
  });

  it("shows the failed status error from the apply result", async () => {
    applyToJobMock.mockResolvedValue({
      status: "failed",
      error: "direct failure",
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() => expect(screen.getByText("direct failure")).toBeInTheDocument());
  });

  it("shows a default error for a failed status without a message", async () => {
    applyToJobMock.mockResolvedValue({
      status: "failed",
      error: null,
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() => expect(screen.getByText("Application failed.")).toBeInTheDocument());
  });

  it("reaches success for a non-queued, non-failed status (queued without a log id)", async () => {
    // status queued but application_log_id null -> skips polling, falls through to success.
    applyToJobMock.mockResolvedValue({
      status: "queued",
      error: null,
      payload: null,
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      expect(
        screen.getByText("Application submitted for Software Engineer at ACME."),
      ).toBeInTheDocument(),
    );
    expect(pollApplicationLog).not.toHaveBeenCalled();
  });

  it("shows the company fallback in the success banner", async () => {
    const jobNoCompany: Job = { ...sampleJob, company: "" };
    applyToJobMock.mockResolvedValue({
      status: "submitted",
      error: null,
      payload: null,
      external_application_id: "ext",
      job: null,
      application_log_id: null,
    });
    renderDialog({ job: jobNoCompany });
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      expect(
        screen.getByText("Application submitted for Software Engineer at this company."),
      ).toBeInTheDocument(),
    );
  });

  it("surfaces an apply error (Error instance)", async () => {
    applyToJobMock.mockRejectedValue(new Error("apply boom"));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() => expect(screen.getByText("apply boom")).toBeInTheDocument());
  });

  it("falls back to a default message for a non-Error apply failure", async () => {
    applyToJobMock.mockRejectedValue("nope");
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    await waitFor(() =>
      // Two banners may exist; assert at least one shows the default message.
      expect(screen.getAllByText("Application failed.").length).toBeGreaterThan(0),
    );
  });

  it("sends the tailored resume artifact id after generating a resume", async () => {
    renderDialog({ initialCoverLetter: "Keep me" });
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() => expect(screen.getByText(/Tailored resume ready:/)).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(mockApi.applyToJob).toHaveBeenCalled());
    expect(mockApi.applyToJob).toHaveBeenCalledWith(sampleJob.id, {
      dry_run: true,
      cover_letter: "Keep me",
      tailored_resume_b64: null,
      tailored_resume_artifact_id: 55,
    });
  });
});
