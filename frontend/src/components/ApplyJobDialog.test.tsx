import { mockApi, resetMockApi } from "../test/mockApi";
import { useState } from "react";
import { fireEvent, screen, waitFor } from "@testing-library/react";
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

describe("ApplyJobDialog", () => {
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

  it("describes the dialog and focuses the container, not Close (FRO-19)", () => {
    renderDialog();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-describedby", "apply-dialog-description");
    expect(dialog).toHaveFocus();
    expect(screen.getByRole("button", { name: "Close" })).not.toHaveFocus();
    expect(document.getElementById("apply-dialog-description")).toHaveTextContent(
      /Review the cover letter/,
    );
  });

  it("announces apply errors via an assertive live region (FRO-19)", async () => {
    applyToJobMock.mockRejectedValue(new Error("Boom"));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Submit application" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
    expect(alert).toHaveClass("banner-error");
    expect(alert).toHaveTextContent("Boom");
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
    pollDocumentGeneration.mockResolvedValue(
      readyCover({ cover_letter: "AI letter", provider: "openai", fallback: false }),
    );
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
    pollDocumentGeneration.mockResolvedValue(
      readyCover({ cover_letter: "Fallback letter", provider: "heuristic", fallback: true }),
    );
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

  it("surfaces a failed document generation status from the poller", async () => {
    pollDocumentGeneration.mockResolvedValue({
      id: 1,
      kind: "cover_letter",
      status: "failed",
      error: "compile failed",
      result: null,
      created_at: "2026-07-10T00:00:00Z",
      updated_at: "2026-07-10T00:00:00Z",
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate cover letter" }));
    await waitFor(() => expect(screen.getByText("compile failed")).toBeInTheDocument());
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
    pollDocumentGeneration.mockResolvedValue(
      readyResume({
        filename: "resume.pdf",
        size_bytes: 10,
        content_sha256: "x",
        pdf_b64: "JVBERi0=",
        artifact_id: 7,
        provider: "gemini",
        fallback: false,
      }),
    );
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByText("Tailored resume generated with gemini.")).toBeInTheDocument(),
    );
  });

  it("shows the fallback resume message", async () => {
    pollDocumentGeneration.mockResolvedValue(
      readyResume({
        filename: "resume.pdf",
        size_bytes: 10,
        content_sha256: "x",
        pdf_b64: "JVBERi0=",
        artifact_id: 8,
        provider: "heuristic",
        fallback: true,
      }),
    );
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

  it("surfaces a failed resume generation status from the poller", async () => {
    pollDocumentGeneration.mockResolvedValue({
      id: 2,
      kind: "resume",
      status: "failed",
      error: null,
      result: null,
      created_at: "2026-07-10T00:00:00Z",
      updated_at: "2026-07-10T00:00:00Z",
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: "Generate tailored resume" }));
    await waitFor(() =>
      expect(screen.getByText("Could not generate a tailored resume.")).toBeInTheDocument(),
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
});
