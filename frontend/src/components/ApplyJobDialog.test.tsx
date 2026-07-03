import { mockApi, resetMockApi } from "../test/mockApi";
import { useState } from "react";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { sampleJob } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import type {
  ApplicationLog,
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
  () => Promise<JobCoverLetterResult>
>;
const generateResumeMock = mockApi.generateResume as unknown as Mock<
  () => Promise<JobResumeResult>
>;

const pollApplicationLog = vi.hoisted(() => vi.fn());
const previewApplicationArtifact = vi.hoisted(() => vi.fn());

vi.mock("../api/pollApplicationLog", () => ({
  pollApplicationLog: (id: number) => pollApplicationLog(id),
}));
vi.mock("../lib/applicationArtifacts", () => ({
  previewApplicationArtifact: (id: number) => previewApplicationArtifact(id),
}));

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

function textarea(): HTMLTextAreaElement {
  return screen.getByRole("textbox") as HTMLTextAreaElement;
}

describe("ApplyJobDialog", () => {
  beforeEach(() => {
    resetMockApi();
    pollApplicationLog.mockReset();
    previewApplicationArtifact.mockReset();
    applyToJobMock.mockResolvedValue({
      status: "dry_run",
      error: null,
      payload: { email: "ada@example.com" },
      external_application_id: null,
      job: null,
      application_log_id: null,
    });
    generateCoverLetterMock.mockResolvedValue({
      cover_letter: "Generated letter",
      provider: "heuristic",
      fallback: false,
    });
    generateResumeMock.mockResolvedValue({
      filename: "resume.pdf",
      size_bytes: 1234,
      content_sha256: "abc",
      pdf_b64: "JVBERi0=",
      artifact_id: 55,
      provider: "heuristic",
      fallback: false,
    });
  });

  it("renders nothing when closed", () => {
    const { container } = renderDialog({ open: false });
    expect(container.firstChild).toBeNull();
  });

  it("shows the profile banner when the profile is not ready", () => {
    renderDialog({ profileReady: false });
    expect(screen.getByRole("link", { name: "application profile" })).toBeInTheDocument();
    expect(screen.queryByText(/Live submission is off/)).not.toBeInTheDocument();
  });

  it("shows the auto-apply banner when live submission is off", () => {
    renderDialog({ profileReady: true, autoApplyEnabled: false });
    expect(screen.getByText(/Live submission is off for this source/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sources" })).toBeInTheDocument();
    // Submit button is disabled because auto-apply is off.
    expect(screen.getByRole("button", { name: "Submit application" })).toBeDisabled();
  });

  it("closes via the Close button", () => {
    const onClose = vi.fn();
    renderDialog({ onClose });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("closes when the backdrop is clicked but not when the dialog is clicked", () => {
    const onClose = vi.fn();
    const { container } = renderDialog({ onClose });
    // Clicking the dialog itself stops propagation.
    fireEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
    // Clicking the backdrop closes.
    fireEvent.click(container.querySelector(".apply-dialog-backdrop")!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("resets state when reopened and reflects the initial cover letter", () => {
    // A harness lets us flip `open`/`initialCoverLetter` without dropping the
    // QueryClientProvider that renderWithClient supplies.
    function Harness() {
      const [open, setOpen] = useState(true);
      const [initial, setInitial] = useState("First");
      return (
        <MemoryRouter>
          <button type="button" onClick={() => setOpen(false)}>
            close-it
          </button>
          <button
            type="button"
            onClick={() => {
              setInitial("Second");
              setOpen(true);
            }}
          >
            reopen-it
          </button>
          <ApplyJobDialog
            job={sampleJob}
            open={open}
            initialCoverLetter={initial}
            profileReady
            autoApplyEnabled
            onClose={() => {}}
          />
        </MemoryRouter>
      );
    }
    renderWithClient(<Harness />);

    expect(textarea().value).toBe("First");
    fireEvent.change(textarea(), { target: { value: "Edited" } });
    expect(textarea().value).toBe("Edited");

    // Close then reopen with a new initial value -> effect resets the field.
    fireEvent.click(screen.getByRole("button", { name: "close-it" }));
    fireEvent.click(screen.getByRole("button", { name: "reopen-it" }));
    expect(textarea().value).toBe("Second");
  });

  it("generates a cover letter from an AI provider", async () => {
    generateCoverLetterMock.mockResolvedValue({
      cover_letter: "AI letter",
      provider: "openai",
      fallback: false,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() => expect(textarea().value).toBe("AI letter"));
    expect(screen.getByText("Draft generated with openai.")).toBeInTheDocument();
  });

  it("shows the heuristic cover letter message", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() =>
      expect(screen.getByText("Draft generated from your profile.")).toBeInTheDocument(),
    );
  });

  it("shows the fallback cover letter message", async () => {
    generateCoverLetterMock.mockResolvedValue({
      cover_letter: "Fallback letter",
      provider: "heuristic",
      fallback: true,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "AI generation was unavailable; a draft was created from your profile instead.",
        ),
      ).toBeInTheDocument(),
    );
  });

  it("surfaces a cover letter generation error (Error instance)", async () => {
    generateCoverLetterMock.mockRejectedValue(new Error("cover boom"));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() => expect(screen.getByText("cover boom")).toBeInTheDocument());
  });

  it("falls back to a default message for a non-Error cover letter failure", async () => {
    generateCoverLetterMock.mockRejectedValue("nope");
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() =>
      expect(screen.getByText("Could not generate a cover letter.")).toBeInTheDocument(),
    );
  });

  it("generates a tailored resume and previews the PDF", async () => {
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() => expect(screen.getByText(/Tailored resume ready:/)).toBeInTheDocument());
    expect(screen.getByText("Tailored resume generated from your profile.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview PDF" }));
    expect(previewApplicationArtifact).toHaveBeenCalledWith(55);
  });

  it("shows the AI resume provider message", async () => {
    generateResumeMock.mockResolvedValue({
      filename: "resume.pdf",
      size_bytes: 10,
      content_sha256: "x",
      pdf_b64: "JVBERi0=",
      artifact_id: 7,
      provider: "gemini",
      fallback: false,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByText("Tailored resume generated with gemini.")).toBeInTheDocument(),
    );
  });

  it("shows the fallback resume message", async () => {
    generateResumeMock.mockResolvedValue({
      filename: "resume.pdf",
      size_bytes: 10,
      content_sha256: "x",
      pdf_b64: "JVBERi0=",
      artifact_id: 8,
      provider: "heuristic",
      fallback: true,
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(
        screen.getByText(
          "AI curation was unavailable; a resume was built from your profile instead.",
        ),
      ).toBeInTheDocument(),
    );
  });

  it("surfaces a resume generation error (Error instance)", async () => {
    generateResumeMock.mockRejectedValue(new Error("resume boom"));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() => expect(screen.getByText("resume boom")).toBeInTheDocument());
  });

  it("falls back to a default message for a non-Error resume failure", async () => {
    generateResumeMock.mockRejectedValue("nope");
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByText("Could not generate a tailored resume.")).toBeInTheDocument(),
    );
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
    let resolveGen: (v: JobCoverLetterResult) => void = () => {};
    generateCoverLetterMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve;
        }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Generating..." })).toBeInTheDocument(),
    );
    expect(textarea()).toBeDisabled();
    resolveGen({ cover_letter: "done", provider: "heuristic", fallback: false });
    await waitFor(() => expect(textarea().value).toBe("done"));
  });

  it("shows the generating label on the resume button while a resume is generating", async () => {
    let resolveGen: (v: JobResumeResult) => void = () => {};
    generateResumeMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve;
        }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Generating..." })).toBeInTheDocument(),
    );
    // The cover letter button keeps its label; only the resume button is busy.
    expect(screen.getByRole("button", { name: "Generate cover letter" })).toBeDisabled();
    resolveGen({
      filename: "resume.pdf",
      size_bytes: 5,
      content_sha256: "y",
      pdf_b64: "JVBERi0=",
      artifact_id: 3,
      provider: "heuristic",
      fallback: false,
    });
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
    generateResumeMock.mockResolvedValue({
      filename: "resume.pdf",
      size_bytes: 10,
      content_sha256: "x",
      pdf_b64: "JVBERi0=",
      // artifact_id null exercises the tailoredResumeArtifactId === null branch.
      artifact_id: null as unknown as number,
      provider: "heuristic",
      fallback: false,
    });
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
