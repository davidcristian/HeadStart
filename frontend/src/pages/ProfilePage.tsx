/** Edit the application profile used by auto-apply. */

import { useEffect, useState } from "react";
import { ExperienceEducationForm } from "../components/profile/ExperienceEducationForm";
import { ApplicationHistoryTable } from "../components/profile/ApplicationHistoryTable";
import {
  EMPTY_PROFILE_FORM,
  ProfileDetailsForm,
  type ProfileFormState,
} from "../components/profile/ProfileDetailsForm";
import { Card } from "../components/ui";
import { useApplicationLogs, useProfile } from "../hooks/queries";
import {
  useDeleteProfile,
  useDeleteResume,
  useSaveProfile,
  useUploadResume,
} from "../hooks/mutations";
import type { EducationEntry, Json, WorkExperienceEntry } from "../types";

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
  const [form, setForm] = useState<ProfileFormState>({ ...EMPTY_PROFILE_FORM });
  const [answers, setAnswers] = useState<Json>({});
  const [workExperience, setWorkExperience] = useState<WorkExperienceEntry[]>([]);
  const [education, setEducation] = useState<EducationEntry[]>([]);
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
    setWorkExperience(data.work_experience ?? []);
    setEducation(data.education ?? []);
  }, [profile.data]);

  function setField<K extends keyof ProfileFormState>(key: K, value: string) {
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
        work_experience: workExperience,
        education,
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
      setForm({ ...EMPTY_PROFILE_FORM });
      setAnswers({});
      setWorkExperience([]);
      setEducation([]);
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

  return (
    <>
      <h1>Application profile</h1>
      <p className="muted">
        The candidate details auto-apply uses when submitting applications on your behalf. Stored
        encrypted at rest and only ever visible to you. Auto-apply is opt-in per source.
      </p>

      <Card title="Your details">
        <ProfileDetailsForm
          form={form}
          answers={answers}
          existing={profile.data}
          error={error}
          saved={saved}
          isPending={profile.isPending}
          answersValid={answersValid}
          uploadPending={uploadResume.isPending}
          deleteResumePending={deleteResume.isPending}
          onFieldChange={setField}
          onAnswersChange={(v, ok) => {
            setAnswers(v);
            setAnswersValid(ok);
            setSaved(false);
          }}
          onResumeSelected={(file) => void onResumeSelected(file)}
          onRemoveResume={() => void removeResume()}
          onSave={() => void save()}
          onClear={() => void clear()}
        />
      </Card>

      <Card title="Experience & education">
        <ExperienceEducationForm
          workExperience={workExperience}
          education={education}
          onWorkExperienceChange={(rows) => {
            setWorkExperience(rows);
            setSaved(false);
          }}
          onEducationChange={(rows) => {
            setEducation(rows);
            setSaved(false);
          }}
        />
      </Card>

      <Card title="Application history">
        <p className="muted">
          Audit log of auto-apply previews and submissions. Enable live auto-apply per source on the
          Sources page.
        </p>
        <ApplicationHistoryTable
          entries={applicationLogs.data}
          isPending={applicationLogs.isPending}
        />
      </Card>
    </>
  );
}
