import { mockApi, resetMockApi } from "../test/mockApi";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { emptyProfile, sampleProfile } from "../test/fixtures";
import { renderWithClient } from "../test/renderWithClient";
import { ProfilePage } from "./ProfilePage";
import type { Profile } from "../types";

describe("ProfilePage", () => {
  beforeEach(() => {
    resetMockApi();
  });

  it("renders the page and empty form", async () => {
    renderWithClient(<ProfilePage />);

    expect(screen.getByRole("heading", { name: "Application profile" })).toBeInTheDocument();
    await waitFor(() => expect(mockApi.getProfile).toHaveBeenCalled());
    expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("");
    // No saved profile yet, so no clear button.
    expect(screen.queryByRole("button", { name: "Clear profile" })).not.toBeInTheDocument();
  });

  it("loads an existing profile into the form", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderWithClient(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("Ada Lovelace"),
    );
    expect(screen.getByPlaceholderText("ada@example.com")).toHaveValue("ada@example.com");
    expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument();
  });

  it("saves the profile", async () => {
    renderWithClient(<ProfilePage />);
    // Wait for the initial fetch to settle (Save is disabled while pending) so the
    // populate-effect cannot overwrite the value we type below.
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled());

    fireEvent.change(screen.getByPlaceholderText("Ada Lovelace"), {
      target: { value: "Grace Hopper" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(mockApi.saveProfile).toHaveBeenCalledWith(
        expect.objectContaining({ full_name: "Grace Hopper" }),
      ),
    );
    await waitFor(() => expect(screen.getByText("Profile saved.")).toBeInTheDocument());
  });

  it("clears an existing profile", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderWithClient(<ProfilePage />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Clear profile" }));

    await waitFor(() => expect(mockApi.deleteProfile).toHaveBeenCalled());
  });

  it("shows application history", async () => {
    mockApi.listApplicationLogs.mockResolvedValue([
      {
        id: 1,
        seen_job_id: 100,
        job_title: "Software Engineer",
        job_company: "ACME",
        job_url: "https://example.test/jobs/1",
        status: "dry_run",
        dry_run: true,
        error: null,
        payload: { email: "ada@example.com" },
        external_application_id: null,
        tailored_resume_artifact: null,
        created_at: "2026-06-28T12:00:00Z",
      },
    ]);
    renderWithClient(<ProfilePage />);

    await waitFor(() => expect(screen.getByText("Software Engineer")).toBeInTheDocument());
    expect(screen.getByText("Preview")).toBeInTheDocument();
  });

  it("surfaces an error when saving fails", async () => {
    mockApi.saveProfile.mockRejectedValueOnce(new Error("save boom"));
    renderWithClient(<ProfilePage />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled());

    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(screen.getByText("save boom")).toBeInTheDocument());
  });

  it("surfaces an error when clearing fails", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    mockApi.deleteProfile.mockRejectedValueOnce(new Error("clear boom"));
    renderWithClient(<ProfilePage />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Clear profile" })).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Clear profile" }));

    await waitFor(() => expect(screen.getByText("clear boom")).toBeInTheDocument());
  });

  it("serializes structured answers and rows into the save payload", async () => {
    mockApi.getProfile.mockResolvedValue(sampleProfile);
    renderWithClient(<ProfilePage />);
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("Ada Lovelace"),
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled());

    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(mockApi.saveProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          answers: { work_authorization: "UK citizen" },
          skills: ["Python"],
          languages: [{ language: "English", proficiency: "Native", is_native: true }],
        }),
      ),
    );
  });

  it("defaults missing profile collections to empty values", async () => {
    const sparse = {
      ...emptyProfile,
      exists: true,
      full_name: "Sparse User",
      answers: null,
      work_experience: null,
      education: null,
      skills: null,
      languages: null,
    } as unknown as Profile;
    mockApi.getProfile.mockResolvedValue(sparse);
    renderWithClient(<ProfilePage />);

    // Wait for the populate-effect to run against the sparse profile so the
    // nullish-coalescing defaults (answers ?? {}, skills ?? [], ...) execute.
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Ada Lovelace")).toHaveValue("Sparse User"),
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(mockApi.saveProfile).toHaveBeenCalledWith(
        expect.objectContaining({
          answers: {},
          work_experience: [],
          education: [],
          skills: [],
          languages: [],
        }),
      ),
    );
    expect(screen.getByText("No skills saved yet.")).toBeInTheDocument();
    expect(screen.getByText("No languages saved yet.")).toBeInTheDocument();
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
