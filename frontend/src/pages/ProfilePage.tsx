/** Edit the application profile used by auto-apply.
 *
 * Holds the candidate data future auto-apply flows submit on the user's behalf:
 * contact details, links, resume text, a cover-letter template, and free-form
 * answers to recurring application questions. Stored encrypted at rest; returned
 * to its owner so it can be reviewed and edited here.
 */

import { useEffect, useState } from "react";
import { JsonEditor } from "../components/JsonEditor";
import { Banner, Button, Card, EmptyState, Field } from "../components/ui";
import { useApplicationLogs, useProfile } from "../hooks/queries";
import {
  useDeleteProfile,
  useDeleteResume,
  useSaveProfile,
  useUploadResume,
} from "../hooks/mutations";
import type { Json } from "../types";

const EMPTY = {
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

function asStringMap(value: Json): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(value)) out[k] = String(v);
  return out;
}

export function ProfilePage() {
  const profile = useProfile();
  const applicationLogs = useApplicationLogs();
  const saveProfile = useSaveProfile();
  const deleteProfile = useDeleteProfile();
  const uploadResume = useUploadResume();
  const deleteResume = useDeleteResume();
  const [form, setForm] = useState({ ...EMPTY });
  const [answers, setAnswers] = useState<Json>({});
  const [answersValid, setAnswersValid] = useState(true);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const data = profile.data;
    if (!data) return;
    setForm({
      full_name: data.full_name,
      email: data.email,
      phone: data.phone,
      location: data.location,
      linkedin: data.links.linkedin,
      github: data.links.github,
      website: data.links.website,
      resume_text: data.resume_text,
      cover_letter_template: data.cover_letter_template,
    });
    setAnswers(data.answers ?? {});
  }, [profile.data]);

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
    setSaved(false);
  }

  async function save() {
    setError(undefined);
    try {
      await saveProfile.mutateAsync({
        full_name: form.full_name,
        email: form.email,
        phone: form.phone,
        location: form.location,
        links: { linkedin: form.linkedin, github: form.github, website: form.website },
        resume_text: form.resume_text,
        cover_letter_template: form.cover_letter_template,
        answers: asStringMap(answers),
      });
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function clear() {
    setError(undefined);
    try {
      await deleteProfile.mutateAsync();
      setForm({ ...EMPTY });
      setAnswers({});
      setSaved(false);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function onResumeSelected(file: File | null) {
    if (!file) return;
    setError(undefined);
    try {
      await uploadResume.mutateAsync(file);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function removeResume() {
    setError(undefined);
    try {
      await deleteResume.mutateAsync();
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1_048_576).toFixed(1)} MB`;
  }

  const existing = profile.data;

  return (
    <>
      <h1>Application profile</h1>
      <p className="muted">
        The candidate details auto-apply uses when submitting applications on your behalf. Stored
        encrypted at rest and only ever visible to you. Auto-apply is opt-in per source.
      </p>

      <Card title="Your details">
        {error && <Banner kind="error">{error}</Banner>}
        {saved && <Banner kind="success">Profile saved.</Banner>}
        {profile.isPending && <p>Loading...</p>}

        <div className="form-grid">
          <Field label="Full name">
            <input
              value={form.full_name}
              onChange={(e) => set("full_name", e.target.value)}
              placeholder="Ada Lovelace"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              placeholder="ada@example.com"
            />
          </Field>
          <Field label="Phone">
            <input
              value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="+1 555 0100"
            />
          </Field>
          <Field label="Location">
            <input
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              placeholder="London, UK"
            />
          </Field>
        </div>

        <div className="form-grid">
          <Field label="LinkedIn">
            <input
              value={form.linkedin}
              onChange={(e) => set("linkedin", e.target.value)}
              placeholder="https://linkedin.com/in/..."
            />
          </Field>
          <Field label="GitHub">
            <input
              value={form.github}
              onChange={(e) => set("github", e.target.value)}
              placeholder="https://github.com/..."
            />
          </Field>
          <Field label="Website">
            <input
              value={form.website}
              onChange={(e) => set("website", e.target.value)}
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
              <Button variant="danger" onClick={removeResume} disabled={deleteResume.isPending}>
                Remove file
              </Button>
            </div>
          ) : (
            <input
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => onResumeSelected(e.target.files?.[0] ?? null)}
              disabled={uploadResume.isPending}
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
            onChange={(e) => set("resume_text", e.target.value)}
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
            onChange={(e) => set("cover_letter_template", e.target.value)}
            placeholder="Dear {company} team, ..."
          />
        </Field>

        <Field
          label="Per-field answers (JSON)"
          hint='Recurring questions, e.g. {"work_authorization": "US citizen", "notice_period": "2 weeks"}'
        >
          <JsonEditor
            value={answers}
            onChange={(v, ok) => {
              setAnswers(v);
              setAnswersValid(ok);
              setSaved(false);
            }}
          />
        </Field>

        <div className="row-actions">
          <Button onClick={save} disabled={!answersValid || profile.isPending}>
            Save profile
          </Button>
          {existing?.exists && (
            <Button variant="danger" onClick={clear}>
              Clear profile
            </Button>
          )}
        </div>
        {existing?.updated_at && (
          <p className="muted">Last updated {new Date(existing.updated_at).toLocaleString()}.</p>
        )}
      </Card>

      <Card title="Application history">
        <p className="muted">
          Audit log of auto-apply previews and submissions. Enable live auto-apply per source on the
          Sources page.
        </p>
        {applicationLogs.isPending && <p>Loading...</p>}
        {applicationLogs.data && applicationLogs.data.length === 0 && (
          <EmptyState>No application attempts yet.</EmptyState>
        )}
        {applicationLogs.data && applicationLogs.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Job</th>
                <th>Result</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {applicationLogs.data.map((entry) => (
                <tr key={entry.id}>
                  <td className="muted">{new Date(entry.created_at).toLocaleString()}</td>
                  <td>
                    <strong>{entry.job_title}</strong>
                    <div className="muted">{entry.job_company}</div>
                  </td>
                  <td>
                    {entry.dry_run ? "Preview" : entry.status}
                    {entry.error && <div className="muted">{entry.error}</div>}
                  </td>
                  <td>
                    {entry.external_application_id && (
                      <div className="muted">ID: {entry.external_application_id}</div>
                    )}
                    {entry.job_url && (
                      <a href={entry.job_url} target="_blank" rel="noreferrer">
                        View posting
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
