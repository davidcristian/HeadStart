import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Profile } from "../../types";
import { emptyProfile } from "../../test/fixtures";
import {
  EMPTY_PROFILE_FORM,
  ProfileDetailsForm,
  type ProfileFormState,
} from "./ProfileDetailsForm";

type Props = React.ComponentProps<typeof ProfileDetailsForm>;

function renderForm(overrides: Partial<Props> = {}) {
  const handlers = {
    onFieldChange: vi.fn(),
    onAnswersChange: vi.fn(),
    onResumeSelected: vi.fn(),
    onRemoveResume: vi.fn(),
    onResumeTemplateSelected: vi.fn(),
    onRemoveResumeTemplate: vi.fn(),
    onSave: vi.fn(),
    onClear: vi.fn(),
  };
  const props: Props = {
    form: { ...EMPTY_PROFILE_FORM },
    answers: {},
    existing: undefined,
    error: undefined,
    saved: false,
    isPending: false,
    answersValid: true,
    uploadPending: false,
    deleteResumePending: false,
    uploadTemplatePending: false,
    deleteTemplatePending: false,
    ...handlers,
    ...overrides,
  };
  const utils = render(<ProfileDetailsForm {...props} />);
  return { ...handlers, ...utils, props };
}

function profileWith(overrides: Partial<Profile>): Profile {
  return { ...emptyProfile, ...overrides };
}

describe("ProfileDetailsForm", () => {
  it("renders the error and success banners plus the loading state", () => {
    renderForm({ error: "Something failed", saved: true, isPending: true });

    expect(screen.getByText("Something failed")).toBeInTheDocument();
    expect(screen.getByText("Profile saved.")).toBeInTheDocument();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("hides the banners and loading state by default", () => {
    renderForm();

    expect(screen.queryByText("Profile saved.")).not.toBeInTheDocument();
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });

  it("reports changes for every text field", () => {
    const { onFieldChange } = renderForm();

    const cases: Array<[string, keyof ProfileFormState, string]> = [
      ["Ada Lovelace", "full_name", "Grace"],
      ["ada@example.com", "email", "g@example.com"],
      ["+1 555 0100", "phone", "+44"],
      ["London, UK", "location", "Paris"],
      ["https://linkedin.com/in/...", "linkedin", "li"],
      ["https://github.com/...", "github", "gh"],
      ["https://...", "website", "site"],
      ["Experience, education, skills...", "resume_text", "resume"],
      ["Dear {company} team, ...", "cover_letter_template", "cover"],
    ];
    for (const [placeholder, key, value] of cases) {
      fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value } });
      expect(onFieldChange).toHaveBeenCalledWith(key, value);
    }
  });

  it("forwards valid and invalid JSON edits from the answers editor", () => {
    const { onAnswersChange } = renderForm();
    const jsonEditor = document.querySelector(".json-editor") as HTMLTextAreaElement;
    expect(jsonEditor).toBeTruthy();

    fireEvent.change(jsonEditor, { target: { value: '{"a": "b"}' } });
    expect(onAnswersChange).toHaveBeenCalledWith({ a: "b" }, true);

    fireEvent.change(jsonEditor, { target: { value: "{ not json" } });
    expect(onAnswersChange).toHaveBeenLastCalledWith({}, false);
  });

  it("shows a file input when no resume file exists and forwards the picked file", () => {
    const { onResumeSelected } = renderForm({ uploadPending: false });

    const fileInput = document.querySelector(
      'input[type="file"][accept*="pdf"]',
    ) as HTMLInputElement;
    expect(fileInput).toBeTruthy();
    expect(fileInput.disabled).toBe(false);

    const file = new File(["x"], "cv.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });
    expect(onResumeSelected).toHaveBeenCalledWith(file);
  });

  it("forwards null when the resume file picker is cleared and disables while uploading", () => {
    const { onResumeSelected } = renderForm({ uploadPending: true });

    const fileInput = document.querySelector(
      'input[type="file"][accept*="pdf"]',
    ) as HTMLInputElement;
    expect(fileInput.disabled).toBe(true);

    fireEvent.change(fileInput, { target: { files: [] } });
    expect(onResumeSelected).toHaveBeenCalledWith(null);
  });

  it("shows an existing resume file with a remove button", () => {
    const { onRemoveResume } = renderForm({
      existing: profileWith({
        resume_file: { filename: "resume.pdf", content_type: "application/pdf", size_bytes: 512 },
      }),
    });

    expect(screen.getByText("resume.pdf (512 B)")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Remove file"));
    expect(onRemoveResume).toHaveBeenCalled();
  });

  it("disables the remove-file button while a delete is pending", () => {
    renderForm({
      existing: profileWith({
        resume_file: { filename: "resume.pdf", content_type: "application/pdf", size_bytes: 2048 },
      }),
      deleteResumePending: true,
    });

    expect(screen.getByText("resume.pdf (2.0 KB)")).toBeInTheDocument();
    expect(screen.getByText("Remove file")).toBeDisabled();
  });

  it("shows a template file input and forwards the picked and cleared template", () => {
    const { onResumeTemplateSelected } = renderForm({ uploadTemplatePending: false });

    const input = document.querySelector('input[type="file"][accept*="tex"]') as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input.disabled).toBe(false);

    const file = new File(["x"], "template.tex", { type: "application/x-tex" });
    fireEvent.change(input, { target: { files: [file] } });
    expect(onResumeTemplateSelected).toHaveBeenCalledWith(file);

    fireEvent.change(input, { target: { files: [] } });
    expect(onResumeTemplateSelected).toHaveBeenLastCalledWith(null);
  });

  it("disables the template file input while uploading", () => {
    renderForm({ uploadTemplatePending: true });

    const input = document.querySelector('input[type="file"][accept*="tex"]') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it("shows a single-format template without the bundle detail", () => {
    const { onRemoveResumeTemplate } = renderForm({
      existing: profileWith({
        resume_template: {
          filename: "resume.tex",
          size_bytes: 1_500_000,
          format: "single",
          entrypoint: null,
          file_count: null,
        },
      }),
    });

    expect(screen.getByText(/resume\.tex \(1\.4 MB\s*\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Remove template"));
    expect(onRemoveResumeTemplate).toHaveBeenCalled();
  });

  it("shows bundle template details and disables removal while pending", () => {
    renderForm({
      existing: profileWith({
        resume_template: {
          filename: "bundle.zip",
          size_bytes: 4096,
          format: "bundle",
          entrypoint: "main.tex",
          file_count: 3,
        },
      }),
      deleteTemplatePending: true,
    });

    expect(
      screen.getByText(/bundle\.zip \(4\.0 KB, 3 files, entry main\.tex\)/),
    ).toBeInTheDocument();
    expect(screen.getByText("Remove template")).toBeDisabled();
  });

  it("shows a bundle template without the detail when file_count is missing", () => {
    renderForm({
      existing: profileWith({
        resume_template: {
          filename: "bundle.zip",
          size_bytes: 100,
          format: "bundle",
          entrypoint: "main.tex",
          file_count: null,
        },
      }),
    });

    expect(screen.getByText(/bundle\.zip \(100 B\s*\)/)).toBeInTheDocument();
    expect(screen.queryByText(/files, entry/)).not.toBeInTheDocument();
  });

  it("saves when the answers are valid and not pending", () => {
    const { onSave } = renderForm();

    const save = screen.getByRole("button", { name: "Save profile" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    expect(onSave).toHaveBeenCalled();
  });

  it("disables Save when answers are invalid", () => {
    renderForm({ answersValid: false });

    expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled();
  });

  it("disables Save while pending", () => {
    renderForm({ isPending: true });

    expect(screen.getByRole("button", { name: "Save profile" })).toBeDisabled();
  });

  it("hides the clear button and last-updated line for a non-existing profile", () => {
    renderForm({ existing: profileWith({ exists: false, updated_at: null }) });

    expect(screen.queryByRole("button", { name: "Clear profile" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Last updated/)).not.toBeInTheDocument();
  });

  it("shows the clear button and last-updated line for an existing profile", () => {
    const { onClear } = renderForm({
      existing: profileWith({ exists: true, updated_at: "2026-06-28T12:00:00Z" }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Clear profile" }));
    expect(onClear).toHaveBeenCalled();
    expect(screen.getByText(/Last updated/)).toBeInTheDocument();
  });
});
