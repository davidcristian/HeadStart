import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const downloadApplicationArtifact = vi.hoisted(() => vi.fn(async () => new Blob(["pdf"])));
vi.mock("../api", () => ({ api: { downloadApplicationArtifact } }));

import {
  downloadApplicationArtifact as downloadArtifact,
  previewApplicationArtifact,
} from "./applicationArtifacts";

beforeEach(() => {
  downloadApplicationArtifact.mockClear();
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:artifact"),
    revokeObjectURL: vi.fn(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("downloadApplicationArtifact", () => {
  it("creates an anchor, clicks it, and revokes the object URL", async () => {
    const anchor = document.createElement("a");
    const clickSpy = vi.spyOn(anchor, "click").mockImplementation(() => {});
    const createElementSpy = vi.spyOn(document, "createElement").mockReturnValue(anchor);

    await downloadArtifact(7, "resume.pdf");

    expect(downloadApplicationArtifact).toHaveBeenCalledWith(7);
    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(createElementSpy).toHaveBeenCalledWith("a");
    expect(anchor.href).toContain("blob:artifact");
    expect(anchor.download).toBe("resume.pdf");
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:artifact");
  });
});

describe("previewApplicationArtifact", () => {
  it("opens the blob in a new tab and revokes the URL later", async () => {
    vi.useFakeTimers();
    const openSpy = vi.spyOn(window, "open").mockReturnValue(null);

    await previewApplicationArtifact(9);

    expect(downloadApplicationArtifact).toHaveBeenCalledWith(9);
    expect(openSpy).toHaveBeenCalledWith("blob:artifact", "_blank", "noopener,noreferrer");
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();

    vi.advanceTimersByTime(60_000);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:artifact");
    vi.useRealTimers();
  });
});
