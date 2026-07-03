/** Download helpers for stored application artifacts. */

import { api } from "../api";

export async function downloadApplicationArtifact(
  artifactId: number,
  filename: string,
): Promise<void> {
  const blob = await api.downloadApplicationArtifact(artifactId);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function previewApplicationArtifact(artifactId: number): Promise<void> {
  const blob = await api.downloadApplicationArtifact(artifactId);
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
