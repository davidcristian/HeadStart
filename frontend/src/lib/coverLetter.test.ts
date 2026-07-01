import { describe, expect, it } from "vitest";
import { renderCoverLetterTemplate } from "./coverLetter";

describe("renderCoverLetterTemplate", () => {
  it("substitutes company and job title placeholders", () => {
    const result = renderCoverLetterTemplate(
      "Dear {company} team, I am excited about {job_title}.",
      "ACME",
      "Platform Engineer",
    );
    expect(result).toBe("Dear ACME team, I am excited about Platform Engineer.");
  });
});
