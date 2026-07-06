/** Helpers for queued cover-letter / resume generation in the apply dialog. */

import { pollDocumentGeneration } from "../api/pollDocumentGeneration";
import type { DocumentGeneration, JobCoverLetterResult, JobResumeResult } from "../types";

export async function awaitCoverLetterGeneration(
  enqueue: (jobId: number) => Promise<DocumentGeneration>,
  jobId: number,
): Promise<JobCoverLetterResult> {
  const queued = await enqueue(jobId);
  const generation = await pollDocumentGeneration(queued.id);
  if (generation.status === "failed") {
    throw new Error(generation.error ?? "Could not generate a cover letter.");
  }
  return generation.result as JobCoverLetterResult;
}

export async function awaitResumeGeneration(
  enqueue: (jobId: number) => Promise<DocumentGeneration>,
  jobId: number,
): Promise<JobResumeResult> {
  const queued = await enqueue(jobId);
  const generation = await pollDocumentGeneration(queued.id);
  if (generation.status === "failed") {
    throw new Error(generation.error ?? "Could not generate a tailored resume.");
  }
  return generation.result as JobResumeResult;
}

export function coverLetterStatusMessage(result: JobCoverLetterResult): string {
  if (result.fallback) {
    return "AI generation was unavailable; a draft was created from your profile instead.";
  }
  if (result.provider !== "heuristic") {
    return `Draft generated with ${result.provider}.`;
  }
  return "Draft generated from your profile.";
}

export function resumeStatusMessage(result: JobResumeResult): string {
  if (result.fallback) {
    return "AI curation was unavailable; a resume was built from your profile instead.";
  }
  if (result.provider !== "heuristic") {
    return `Tailored resume generated with ${result.provider}.`;
  }
  return "Tailored resume generated from your profile.";
}
