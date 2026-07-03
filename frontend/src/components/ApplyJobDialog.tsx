/** Confirm and submit (or preview) an auto-apply for one job. */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { pollApplicationLog } from "../api/pollApplicationLog";
import { previewApplicationArtifact } from "../lib/applicationArtifacts";
import { Banner, Button, Field } from "./ui";
import { useApplyToJob, useGenerateCoverLetter, useGenerateResume } from "../hooks/mutations";
import { useFocusTrap } from "../hooks/useFocusTrap";
import type { Job, JobApplyResult } from "../types";

type Step = "edit" | "preview" | "success";

export function ApplyJobDialog({
  job,
  open,
  initialCoverLetter,
  profileReady,
  autoApplyEnabled,
  onClose,
}: {
  job: Job;
  open: boolean;
  initialCoverLetter: string;
  profileReady: boolean;
  autoApplyEnabled: boolean;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const qc = useQueryClient();
  const { mutateAsync, reset, isPending } = useApplyToJob();
  const {
    mutateAsync: generateCoverLetterAsync,
    reset: resetGenerateCoverLetter,
    isPending: isGeneratingCoverLetter,
  } = useGenerateCoverLetter();
  const {
    mutateAsync: generateResumeAsync,
    reset: resetGenerateResume,
    isPending: isGeneratingResume,
  } = useGenerateResume();
  const [coverLetter, setCoverLetter] = useState(initialCoverLetter);
  const [tailoredResumeB64, setTailoredResumeB64] = useState<string | null>(null);
  const [tailoredResumeArtifactId, setTailoredResumeArtifactId] = useState<number | null>(null);
  const [tailoredResumeLabel, setTailoredResumeLabel] = useState<string | null>(null);
  const [step, setStep] = useState<Step>("edit");
  const [preview, setPreview] = useState<JobApplyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generateMessage, setGenerateMessage] = useState<string | null>(null);
  const [resumeMessage, setResumeMessage] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"preview" | "submit" | null>(null);

  useFocusTrap(open, dialogRef, onClose);

  useEffect(() => {
    if (!open) return;
    setCoverLetter(initialCoverLetter);
    setTailoredResumeB64(null);
    setTailoredResumeArtifactId(null);
    setTailoredResumeLabel(null);
    setStep("edit");
    setPreview(null);
    setError(null);
    setGenerateMessage(null);
    setResumeMessage(null);
    setBusyAction(null);
    reset();
    resetGenerateCoverLetter();
    resetGenerateResume();
  }, [open, job.id, initialCoverLetter, reset, resetGenerateCoverLetter, resetGenerateResume]);

  if (!open) return null;

  async function runGenerateCoverLetter() {
    setError(null);
    setGenerateMessage(null);
    try {
      const result = await generateCoverLetterAsync(job.id);
      setCoverLetter(result.cover_letter);
      if (result.fallback) {
        setGenerateMessage(
          "AI generation was unavailable; a draft was created from your profile instead.",
        );
      } else if (result.provider !== "heuristic") {
        setGenerateMessage(`Draft generated with ${result.provider}.`);
      } else {
        setGenerateMessage("Draft generated from your profile.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a cover letter.");
    }
  }

  async function runGenerateResume() {
    setError(null);
    setResumeMessage(null);
    try {
      const result = await generateResumeAsync(job.id);
      setTailoredResumeB64(result.pdf_b64);
      setTailoredResumeArtifactId(result.artifact_id);
      setTailoredResumeLabel(`${result.filename} (${result.size_bytes.toLocaleString()} bytes)`);
      if (result.fallback) {
        setResumeMessage(
          "AI curation was unavailable; a resume was built from your profile instead.",
        );
      } else if (result.provider !== "heuristic") {
        setResumeMessage(`Tailored resume generated with ${result.provider}.`);
      } else {
        setResumeMessage("Tailored resume generated from your profile.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a tailored resume.");
    }
  }

  async function runApply(dryRun: boolean) {
    setError(null);
    setBusyAction(dryRun ? "preview" : "submit");
    try {
      const result = await mutateAsync({
        id: job.id,
        dry_run: dryRun,
        cover_letter: coverLetter.trim() || null,
        tailored_resume_b64: tailoredResumeArtifactId ? null : tailoredResumeB64,
        tailored_resume_artifact_id: tailoredResumeArtifactId,
      });
      if (dryRun) {
        setPreview(result);
        setStep("preview");
        return;
      }
      if (result.status === "queued" && result.application_log_id != null) {
        const log = await pollApplicationLog(result.application_log_id);
        if (log.status === "failed") {
          setError(log.error ?? "Application failed.");
          return;
        }
        await qc.invalidateQueries({ queryKey: ["jobs"] });
        setStep("success");
        return;
      }
      if (result.status === "failed") {
        setError(result.error ?? "Application failed.");
        return;
      }
      setStep("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Application failed.");
    } finally {
      setBusyAction(null);
    }
  }

  const generationBusy = isGeneratingCoverLetter || isGeneratingResume;

  return (
    <div className="apply-dialog-backdrop" onClick={onClose}>
      <div
        className="apply-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="apply-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="apply-dialog-header">
          <h2 id="apply-dialog-title">Apply to {job.title}</h2>
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            Close
          </Button>
        </header>

        {!profileReady && (
          <Banner kind="info">
            Save an{" "}
            <Link to="/app/profile" onClick={onClose}>
              application profile
            </Link>{" "}
            before submitting.
          </Banner>
        )}

        {profileReady && !autoApplyEnabled && (
          <Banner kind="info">
            Live submission is off for this source. You can preview the payload, then enable
            auto-apply on the{" "}
            <Link to="/app/sources" onClick={onClose}>
              Sources
            </Link>{" "}
            page before submitting.
          </Banner>
        )}

        {step === "success" ? (
          <div className="apply-dialog-body">
            <Banner kind="success">
              Application submitted for {job.title} at {job.company || "this company"}.
            </Banner>
            <div className="row-actions">
              <Button onClick={onClose}>Done</Button>
            </div>
          </div>
        ) : (
          <div className="apply-dialog-body">
            <p className="muted">
              Review the cover letter below. Generate drafts a tailored letter and resume from your
              profile; preview shows the payload that will be sent.
            </p>
            <Field
              label="Cover letter"
              hint="Optional. Overrides your profile template for this job."
            >
              <textarea
                rows={8}
                value={coverLetter}
                onChange={(event) => setCoverLetter(event.target.value)}
                disabled={isPending || generationBusy}
              />
            </Field>
            <div className="row-actions apply-dialog-actions">
              <Button
                variant="ghost"
                onClick={() => void runGenerateCoverLetter()}
                disabled={!profileReady || isPending || generationBusy}
              >
                {isGeneratingCoverLetter ? "Generating..." : "Generate cover letter"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => void runGenerateResume()}
                disabled={!profileReady || isPending || generationBusy}
              >
                {isGeneratingResume ? "Generating..." : "Generate tailored resume"}
              </Button>
            </div>

            {tailoredResumeLabel && (
              <div className="row-actions apply-tailored-resume-meta">
                <p className="muted">Tailored resume ready: {tailoredResumeLabel}</p>
                {tailoredResumeArtifactId !== null && (
                  <Button
                    variant="ghost"
                    onClick={() => void previewApplicationArtifact(tailoredResumeArtifactId)}
                  >
                    Preview PDF
                  </Button>
                )}
              </div>
            )}

            {generateMessage && <Banner kind="info">{generateMessage}</Banner>}
            {resumeMessage && <Banner kind="info">{resumeMessage}</Banner>}

            {step === "preview" && preview?.payload && (
              <details className="apply-preview" open>
                <summary>Application preview</summary>
                <pre>{JSON.stringify(preview.payload, null, 2)}</pre>
              </details>
            )}

            {error && <Banner kind="error">{error}</Banner>}

            <div className="row-actions apply-dialog-actions">
              <Button
                variant="ghost"
                onClick={() => void runApply(true)}
                disabled={!profileReady || isPending || generationBusy}
              >
                {busyAction === "preview" ? "Previewing..." : "Preview"}
              </Button>
              <Button
                onClick={() => void runApply(false)}
                disabled={
                  !profileReady ||
                  !autoApplyEnabled ||
                  isPending ||
                  generationBusy ||
                  busyAction === "submit"
                }
              >
                {busyAction === "submit" ? "Submitting..." : "Submit application"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
