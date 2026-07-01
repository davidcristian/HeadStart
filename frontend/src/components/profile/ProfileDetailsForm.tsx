/** Profile details form for auto-apply. */

import { JsonEditor } from "../JsonEditor";
import { Banner, Button, Field } from "../ui";
import type { Json, Profile } from "../../types";

export const EMPTY_PROFILE_FORM = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  linkedin: "",
  github: "",
  website: "",
  resume_text: "",
  cover_letter_template: "",
};

export type ProfileFormState = typeof EMPTY_PROFILE_FORM;

interface ProfileDetailsFormProps {
  form: ProfileFormState;
  answers: Json;
  existing: Profile | undefined;
  error: string | undefined;
  saved: boolean;
  isPending: boolean;
  answersValid: boolean;
  uploadPending: boolean;
  deleteResumePending: boolean;
  onFieldChange: <K extends keyof ProfileFormState>(key: K, value: string) => void;
  onAnswersChange: (value: Json, valid: boolean) => void;
  onResumeSelected: (file: File | null) => void;
  onRemoveResume: () => void;
  onSave: () => void;
  onClear: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export function ProfileDetailsForm({
  form,
  answers,
  existing,
  error,
  saved,
  isPending,
  answersValid,
  uploadPending,
  deleteResumePending,
  onFieldChange,
  onAnswersChange,
  onResumeSelected,
  onRemoveResume,
  onSave,
  onClear,
}: ProfileDetailsFormProps) {
  return (
    <>
      {error && <Banner kind="error">{error}</Banner>}
      {saved && <Banner kind="success">Profile saved.</Banner>}
      {isPending && <p>Loading...</p>}

      <div className="form-grid">
        <Field label="Full name">
          <input
            value={form.full_name}
            onChange={(e) => onFieldChange("full_name", e.target.value)}
            placeholder="Ada Lovelace"
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            value={form.email}
            onChange={(e) => onFieldChange("email", e.target.value)}
            placeholder="ada@example.com"
          />
        </Field>
        <Field label="Phone">
          <input
            value={form.phone}
            onChange={(e) => onFieldChange("phone", e.target.value)}
            placeholder="+1 555 0100"
          />
        </Field>
        <Field label="Location">
          <input
            value={form.location}
            onChange={(e) => onFieldChange("location", e.target.value)}
            placeholder="London, UK"
          />
        </Field>
      </div>

      <div className="form-grid">
        <Field label="LinkedIn">
          <input
            value={form.linkedin}
            onChange={(e) => onFieldChange("linkedin", e.target.value)}
            placeholder="https://linkedin.com/in/..."
          />
        </Field>
        <Field label="GitHub">
          <input
            value={form.github}
            onChange={(e) => onFieldChange("github", e.target.value)}
            placeholder="https://github.com/..."
          />
        </Field>
        <Field label="Website">
          <input
            value={form.website}
            onChange={(e) => onFieldChange("website", e.target.value)}
            placeholder="https://..."
          />
        </Field>
      </div>

      <Field
        label="Resume file"
        hint="PDF or Word document attached when auto-applying (up to 2 MB). Optional if you use plain-text resume below."
      >
        {existing?.resume_file ? (
          <div className="row-actions">
            <span>
              {existing.resume_file.filename} ({formatFileSize(existing.resume_file.size_bytes)})
            </span>
            <Button variant="danger" onClick={onRemoveResume} disabled={deleteResumePending}>
              Remove file
            </Button>
          </div>
        ) : (
          <input
            type="file"
            accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => onResumeSelected(e.target.files?.[0] ?? null)}
            disabled={uploadPending}
          />
        )}
      </Field>

      <Field
        label="Resume / CV (plain text)"
        hint="Optional fallback when no file is uploaded; also appended to comments on some boards."
      >
        <textarea
          rows={8}
          value={form.resume_text}
          onChange={(e) => onFieldChange("resume_text", e.target.value)}
          placeholder="Experience, education, skills..."
        />
      </Field>

      <Field
        label="Cover-letter template"
        hint="Optional. Use {company} and {title} as placeholders."
      >
        <textarea
          rows={6}
          value={form.cover_letter_template}
          onChange={(e) => onFieldChange("cover_letter_template", e.target.value)}
          placeholder="Dear {company} team, ..."
        />
      </Field>

      <Field
        label="Per-field answers (JSON)"
        hint='Recurring questions, e.g. {"work_authorization": "US citizen", "notice_period": "2 weeks"}'
      >
        <JsonEditor value={answers} onChange={onAnswersChange} />
      </Field>

      <div className="row-actions">
        <Button onClick={onSave} disabled={!answersValid || isPending}>
          Save profile
        </Button>
        {existing?.exists && (
          <Button variant="danger" onClick={onClear}>
            Clear profile
          </Button>
        )}
      </div>
      {existing?.updated_at && (
        <p className="muted">Last updated {new Date(existing.updated_at).toLocaleString()}.</p>
      )}
    </>
  );
}
