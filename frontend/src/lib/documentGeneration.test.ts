import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DocumentGeneration, JobCoverLetterResult, JobResumeResult } from "../types";
import {
  awaitCoverLetterGeneration,
  awaitResumeGeneration,
  coverLetterStatusMessage,
  resumeStatusMessage,
} from "./documentGeneration";

const pollDocumentGeneration = vi.hoisted(() => vi.fn());
vi.mock("../api/pollDocumentGeneration", () => ({
  pollDocumentGeneration: (id: number) => pollDocumentGeneration(id),
}));

function queued(kind: DocumentGeneration["kind"], id: number): DocumentGeneration {
  return {
    id,
    kind,
    status: "queued",
    error: null,
    result: null,
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}

beforeEach(() => {
  pollDocumentGeneration.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("awaitCoverLetterGeneration", () => {
  it("returns the ready cover letter result", async () => {
    const result: JobCoverLetterResult = {
      cover_letter: "hi",
      provider: "heuristic",
      fallback: false,
    };
    pollDocumentGeneration.mockResolvedValue({
      ...queued("cover_letter", 1),
      status: "ready",
      result,
    });
    await expect(
      awaitCoverLetterGeneration(async () => queued("cover_letter", 1), 9),
    ).resolves.toEqual(result);
  });

  it("throws when generation failed", async () => {
    pollDocumentGeneration.mockResolvedValue({
      ...queued("cover_letter", 1),
      status: "failed",
      error: "boom",
    });
    await expect(
      awaitCoverLetterGeneration(async () => queued("cover_letter", 1), 9),
    ).rejects.toThrow("boom");
  });

  it("uses a default error when failed without a message", async () => {
    pollDocumentGeneration.mockResolvedValue({
      ...queued("cover_letter", 1),
      status: "failed",
      error: null,
    });
    await expect(
      awaitCoverLetterGeneration(async () => queued("cover_letter", 1), 9),
    ).rejects.toThrow(/Could not generate a cover letter/);
  });
});

describe("awaitResumeGeneration", () => {
  it("returns the ready resume result", async () => {
    const result: JobResumeResult = {
      filename: "r.pdf",
      size_bytes: 1,
      content_sha256: "x",
      pdf_b64: "JVBERi0=",
      artifact_id: 3,
      provider: "openai",
      fallback: false,
    };
    pollDocumentGeneration.mockResolvedValue({
      ...queued("resume", 2),
      status: "ready",
      result,
    });
    await expect(awaitResumeGeneration(async () => queued("resume", 2), 9)).resolves.toEqual(
      result,
    );
  });

  it("throws when generation failed", async () => {
    pollDocumentGeneration.mockResolvedValue({
      ...queued("resume", 2),
      status: "failed",
      error: null,
    });
    await expect(awaitResumeGeneration(async () => queued("resume", 2), 9)).rejects.toThrow(
      /Could not generate a tailored resume/,
    );
  });
});

describe("status messages", () => {
  it("describes cover letter outcomes", () => {
    expect(
      coverLetterStatusMessage({ cover_letter: "x", provider: "heuristic", fallback: false }),
    ).toMatch(/from your profile/);
    expect(
      coverLetterStatusMessage({ cover_letter: "x", provider: "openai", fallback: false }),
    ).toMatch(/openai/);
    expect(
      coverLetterStatusMessage({ cover_letter: "x", provider: "heuristic", fallback: true }),
    ).toMatch(/unavailable/);
    expect(
      coverLetterStatusMessage({
        cover_letter: "x",
        provider: "heuristic",
        fallback: false,
        injection_guarded: true,
      }),
    ).toMatch(/unsafe for AI/);
  });

  it("describes resume outcomes", () => {
    expect(
      resumeStatusMessage({
        filename: "r.pdf",
        size_bytes: 1,
        content_sha256: "x",
        pdf_b64: "x",
        artifact_id: 1,
        provider: "heuristic",
        fallback: false,
      }),
    ).toMatch(/from your profile/);
    expect(
      resumeStatusMessage({
        filename: "r.pdf",
        size_bytes: 1,
        content_sha256: "x",
        pdf_b64: "x",
        artifact_id: 1,
        provider: "gemini",
        fallback: false,
      }),
    ).toMatch(/gemini/);
    expect(
      resumeStatusMessage({
        filename: "r.pdf",
        size_bytes: 1,
        content_sha256: "x",
        pdf_b64: "x",
        artifact_id: 1,
        provider: "heuristic",
        fallback: true,
      }),
    ).toMatch(/unavailable/);
  });
});
