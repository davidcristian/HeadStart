/** Client preflight for profile resume/template uploads (mirrors backend caps). */

/** Default `PROFILE_RESUME_MAX_BYTES` (2 MiB). */
export const PROFILE_RESUME_MAX_BYTES = 2_097_152;
/** Default `PROFILE_RESUME_TEMPLATE_MAX_BYTES` (512 KiB). */
export const PROFILE_RESUME_TEMPLATE_MAX_BYTES = 524_288;
/** Default `PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES` (2 MiB). */
export const PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES = 2_097_152;

const RESUME_EXTENSIONS = [".pdf", ".doc", ".docx"] as const;

function fileExtension(name: string): string {
  const lower = name.trim().toLowerCase();
  const dot = lower.lastIndexOf(".");
  return dot >= 0 ? lower.slice(dot) : "";
}

/** Return an error message when the resume file fails size/extension preflight. */
export function validateResumeUpload(file: File): string | null {
  const name = file.name.trim();
  if (!name) return "Resume filename is required";
  const ext = fileExtension(name);
  if (!(RESUME_EXTENSIONS as readonly string[]).includes(ext)) {
    return "Resume must be a PDF or Word document (.pdf, .doc, or .docx)";
  }
  if (file.size === 0) return "Resume file is empty";
  if (file.size > PROFILE_RESUME_MAX_BYTES) {
    return `Resume file exceeds the ${PROFILE_RESUME_MAX_BYTES / 1_048_576} MB limit`;
  }
  return null;
}

/** Return an error message when the LaTeX template fails size/extension preflight. */
export function validateResumeTemplateUpload(file: File): string | null {
  const name = file.name.trim();
  if (!name) return "Resume template filename is required";
  if (file.size === 0) return "Resume template file is empty";
  const ext = fileExtension(name);
  if (ext === ".zip") {
    if (file.size > PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES) {
      return `Resume template bundle exceeds the ${PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES / 1_048_576} MB limit`;
    }
    return null;
  }
  if (ext !== ".tex") {
    return "Resume template must be a .tex file or .zip bundle";
  }
  if (file.size > PROFILE_RESUME_TEMPLATE_MAX_BYTES) {
    return `Resume template exceeds the ${PROFILE_RESUME_TEMPLATE_MAX_BYTES / 1024} KB limit`;
  }
  return null;
}
