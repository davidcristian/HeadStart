import { describe, expect, it } from "vitest";
import {
  PROFILE_RESUME_MAX_BYTES,
  PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES,
  PROFILE_RESUME_TEMPLATE_MAX_BYTES,
  validateResumeTemplateUpload,
  validateResumeUpload,
} from "./profileUploadValidation";

describe("validateResumeUpload", () => {
  it("accepts a PDF under the size cap", () => {
    const file = new File(["cv"], "cv.pdf", { type: "application/pdf" });
    expect(validateResumeUpload(file)).toBeNull();
  });

  it("rejects an empty filename", () => {
    const file = new File(["cv"], "   ", { type: "application/pdf" });
    expect(validateResumeUpload(file)).toBe("Resume filename is required");
  });

  it("rejects a disallowed extension", () => {
    const file = new File(["x"], "notes.txt", { type: "text/plain" });
    expect(validateResumeUpload(file)).toBe(
      "Resume must be a PDF or Word document (.pdf, .doc, or .docx)",
    );
  });

  it("rejects a filename with no extension", () => {
    const file = new File(["x"], "resume", { type: "application/pdf" });
    expect(validateResumeUpload(file)).toBe(
      "Resume must be a PDF or Word document (.pdf, .doc, or .docx)",
    );
  });

  it("rejects an empty file", () => {
    const file = new File([], "empty.pdf", { type: "application/pdf" });
    expect(validateResumeUpload(file)).toBe("Resume file is empty");
  });

  it("rejects a file over the 2 MB cap without uploading", () => {
    const oversized = new File([new Uint8Array(PROFILE_RESUME_MAX_BYTES + 1)], "big.pdf", {
      type: "application/pdf",
    });
    expect(validateResumeUpload(oversized)).toBe("Resume file exceeds the 2 MB limit");
  });
});

describe("validateResumeTemplateUpload", () => {
  it("accepts a .tex file under the single-file cap", () => {
    const file = new File(["\\documentclass{article}"], "resume.tex", {
      type: "application/x-tex",
    });
    expect(validateResumeTemplateUpload(file)).toBeNull();
  });

  it("accepts a .zip bundle under the bundle cap", () => {
    const file = new File([new Uint8Array(64)], "bundle.zip", { type: "application/zip" });
    expect(validateResumeTemplateUpload(file)).toBeNull();
  });

  it("rejects an empty filename", () => {
    const file = new File(["x"], "  ", { type: "application/x-tex" });
    expect(validateResumeTemplateUpload(file)).toBe("Resume template filename is required");
  });

  it("rejects an empty file", () => {
    const file = new File([], "empty.tex", { type: "application/x-tex" });
    expect(validateResumeTemplateUpload(file)).toBe("Resume template file is empty");
  });

  it("rejects a non-.tex/.zip extension", () => {
    const file = new File(["x"], "resume.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    expect(validateResumeTemplateUpload(file)).toBe(
      "Resume template must be a .tex file or .zip bundle",
    );
  });

  it("rejects a .tex file over the 512 KB cap", () => {
    const oversized = new File([new Uint8Array(PROFILE_RESUME_TEMPLATE_MAX_BYTES + 1)], "big.tex", {
      type: "application/x-tex",
    });
    expect(validateResumeTemplateUpload(oversized)).toBe(
      "Resume template exceeds the 512 KB limit",
    );
  });

  it("rejects a .zip bundle over the 2 MB cap", () => {
    const oversized = new File(
      [new Uint8Array(PROFILE_RESUME_TEMPLATE_BUNDLE_MAX_BYTES + 1)],
      "big.zip",
      { type: "application/zip" },
    );
    expect(validateResumeTemplateUpload(oversized)).toBe(
      "Resume template bundle exceeds the 2 MB limit",
    );
  });
});
