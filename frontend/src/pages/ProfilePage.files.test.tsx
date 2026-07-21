import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { sampleProfile } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { ProfilePage } from "./ProfilePage";

describe("ProfilePage files and structured editing", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("uploads a resume file", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    const input = document.querySelector<HTMLInputElement>('input[accept*=".pdf"]');
    expect(input).not.toBeNull();
    const file = new File(["cv"], "cv.pdf", { type: "application/pdf" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() => expect(mockApi.uploadResume).toHaveBeenCalledWith(file));
    await waitFor(() => expect(screen.getByText("Profile saved.")).toBeInTheDocument());
  });

  it("ignores a resume selection with no file", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    mockApi.uploadResume.mockClear();
    const input = document.querySelector<HTMLInputElement>('input[accept*=".pdf"]');
    fireEvent.change(input as HTMLInputElement, { target: { files: [] } });

    expect(mockApi.uploadResume).not.toHaveBeenCalled();
  });

  it("surfaces an error when uploading a resume fails", async () => {
    mockApi.uploadResume.mockRejectedValueOnce(new Error("upload boom"));
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    const input = document.querySelector<HTMLInputElement>('input[accept*=".pdf"]');
    const file = new File(["cv"], "cv.pdf", { type: "application/pdf" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("upload boom")).toBeInTheDocument());
  });

  it("rejects an oversized resume before calling the upload API", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    mockApi.uploadResume.mockClear();
    const input = document.querySelector<HTMLInputElement>('input[accept*=".pdf"]');
    const file = new File([new Uint8Array(2_097_153)], "huge.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() =>
      expect(screen.getByText("Resume file exceeds the 2 MB limit")).toBeInTheDocument(),
    );
    expect(mockApi.uploadResume).not.toHaveBeenCalled();
  });

  it("rejects a resume with a disallowed extension before upload", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    mockApi.uploadResume.mockClear();
    const input = document.querySelector<HTMLInputElement>('input[accept*=".pdf"]');
    const file = new File(["x"], "notes.txt", { type: "text/plain" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() =>
      expect(
        screen.getByText("Resume must be a PDF or Word document (.pdf, .doc, or .docx)"),
      ).toBeInTheDocument(),
    );
    expect(mockApi.uploadResume).not.toHaveBeenCalled();
  });

  it("removes an existing resume file", async () => {
    const withResume = {
      ...sampleProfile,
      resume_file: { filename: "cv.pdf", content_type: "application/pdf", size_bytes: 2048 },
    };
    mockApi.getProfile.mockResolvedValue(withResume);
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Remove file")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Remove file"));

    await waitFor(() => expect(mockApi.deleteResume).toHaveBeenCalled());
  });

  it("surfaces an error when removing a resume fails", async () => {
    const withResume = {
      ...sampleProfile,
      resume_file: { filename: "cv.pdf", content_type: "application/pdf", size_bytes: 2048 },
    };
    mockApi.getProfile.mockResolvedValue(withResume);
    mockApi.deleteResume.mockRejectedValueOnce(new Error("remove boom"));
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Remove file")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Remove file"));

    await waitFor(() => expect(screen.getByText("remove boom")).toBeInTheDocument());
  });

  it("surfaces an error when uploading a template fails", async () => {
    mockApi.uploadResumeTemplate.mockRejectedValueOnce(new Error("template boom"));
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    const input = document.querySelector<HTMLInputElement>('input[accept*=".tex"]');
    const file = new File(["\\documentclass"], "tmpl.tex", { type: "application/x-tex" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByText("template boom")).toBeInTheDocument());
  });

  it("rejects an oversized .tex template before calling the upload API", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    mockApi.uploadResumeTemplate.mockClear();
    const input = document.querySelector<HTMLInputElement>('input[accept*=".tex"]');
    const file = new File([new Uint8Array(524_289)], "huge.tex", {
      type: "application/x-tex",
    });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() =>
      expect(screen.getByText("Resume template exceeds the 512 KB limit")).toBeInTheDocument(),
    );
    expect(mockApi.uploadResumeTemplate).not.toHaveBeenCalled();
  });

  it("uploads a resume template", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    const input = document.querySelector<HTMLInputElement>('input[accept*=".tex"]');
    expect(input).not.toBeNull();
    const file = new File(["\\documentclass"], "tmpl.tex", { type: "application/x-tex" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });

    await waitFor(() => expect(mockApi.uploadResumeTemplate).toHaveBeenCalledWith(file));
    await waitFor(() => expect(screen.getByText("Profile saved.")).toBeInTheDocument());
  });

  it("ignores a template selection with no file", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    mockApi.uploadResumeTemplate.mockClear();
    const input = document.querySelector<HTMLInputElement>('input[accept*=".tex"]');
    fireEvent.change(input as HTMLInputElement, { target: { files: [] } });

    expect(mockApi.uploadResumeTemplate).not.toHaveBeenCalled();
  });

  it("removes an existing resume template", async () => {
    const withTemplate = {
      ...sampleProfile,
      resume_template: {
        filename: "tmpl.tex",
        size_bytes: 512,
        format: "single" as const,
        entrypoint: null,
        file_count: null,
      },
    };
    mockApi.getProfile.mockResolvedValue(withTemplate);
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Remove template")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Remove template"));

    await waitFor(() => expect(mockApi.deleteResumeTemplate).toHaveBeenCalled());
  });

  it("surfaces an error when removing a template fails", async () => {
    const withTemplate = {
      ...sampleProfile,
      resume_template: {
        filename: "tmpl.tex",
        size_bytes: 512,
        format: "single" as const,
        entrypoint: null,
        file_count: null,
      },
    };
    mockApi.getProfile.mockResolvedValue(withTemplate);
    mockApi.deleteResumeTemplate.mockRejectedValueOnce(new Error("template remove boom"));
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Remove template")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Remove template"));

    await waitFor(() => expect(screen.getByText("template remove boom")).toBeInTheDocument());
  });

  it("edits answers, experience, education, skills and languages", async () => {
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());

    const jsonEditor = document.querySelector<HTMLTextAreaElement>("textarea.json-editor");
    expect(jsonEditor).not.toBeNull();
    fireEvent.change(jsonEditor as HTMLTextAreaElement, {
      target: { value: '{"work_authorization":"US citizen"}' },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add role" }));
    fireEvent.click(screen.getByRole("button", { name: "Add school" }));
    fireEvent.click(screen.getByRole("button", { name: "Add skill" }));
    fireEvent.click(screen.getByRole("button", { name: "Add language" }));

    expect(screen.getByText("Role 1")).toBeInTheDocument();
    expect(screen.getByText("School 1")).toBeInTheDocument();
    expect(screen.getByText("Skill 1")).toBeInTheDocument();
    expect(screen.getByText("Language 1")).toBeInTheDocument();
  });
});
