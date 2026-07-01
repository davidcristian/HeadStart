/** Substitute simple placeholders in a cover-letter template. */

export function renderCoverLetterTemplate(
  template: string,
  company: string,
  jobTitle: string,
): string {
  return template
    .replaceAll("{company}", company)
    .replaceAll("{job_title}", jobTitle)
    .replaceAll("{title}", jobTitle);
}
