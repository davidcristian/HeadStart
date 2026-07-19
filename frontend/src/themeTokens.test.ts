import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "index.css"), "utf8");

describe("theme tokens (FRO-33)", () => {
  it("defines --surface, --accent, and --bg-muted as aliases of existing palette tokens", () => {
    // Cookie-consent / portal / reply-draft styles reference these names; without
    // :root definitions they resolve invalid and paint transparent.
    expect(css).toMatch(/--surface:\s*var\(--bg-elev\)/);
    expect(css).toMatch(/--bg-muted:\s*var\(--bg-elev-2\)/);
    expect(css).toMatch(/--accent:\s*var\(--brand\)/);
  });
});
