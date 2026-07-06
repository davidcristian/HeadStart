/** Document-generation fixtures for mockApi (kept separate for the LOC cap). */

export const sampleQueuedCoverLetterGeneration = {
  id: 1,
  kind: "cover_letter" as const,
  status: "queued" as const,
  error: null,
  result: null,
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
};

export const sampleQueuedResumeGeneration = {
  id: 2,
  kind: "resume" as const,
  status: "queued" as const,
  error: null,
  result: null,
  created_at: "2026-07-10T00:00:00Z",
  updated_at: "2026-07-10T00:00:00Z",
};

export function sampleDocumentGeneration(id: number) {
  if (id === 2) {
    return {
      id: 2,
      kind: "resume" as const,
      status: "ready" as const,
      error: null,
      result: {
        filename: "resume-ACME-Software-Engineer.pdf",
        size_bytes: 128,
        content_sha256: "abc123",
        pdf_b64: "JVBERi0xLjQK",
        artifact_id: 55,
        provider: "heuristic",
        fallback: false,
      },
      created_at: "2026-07-10T00:00:00Z",
      updated_at: "2026-07-10T00:00:00Z",
    };
  }
  return {
    id: 1,
    kind: "cover_letter" as const,
    status: "ready" as const,
    error: null,
    result: {
      cover_letter: "Dear ACME team,\n\nI am excited about the Software Engineer role.",
      provider: "heuristic",
      fallback: false,
    },
    created_at: "2026-07-10T00:00:00Z",
    updated_at: "2026-07-10T00:00:00Z",
  };
}
