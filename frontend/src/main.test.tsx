import { beforeEach, describe, expect, it, vi } from "vitest";

const render = vi.fn();
const createRoot = vi.fn(() => ({ render }));
const registerSW = vi.fn();

vi.mock("react-dom/client", () => ({
  default: { createRoot },
  createRoot,
}));
vi.mock("virtual:pwa-register", () => ({ registerSW }));

describe("main entry point", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = '<div id="root"></div>';
    vi.resetModules();
  });

  it("registers the service worker and mounts the app into #root", async () => {
    await import("./main");

    expect(registerSW).toHaveBeenCalledWith({ immediate: true });
    expect(createRoot).toHaveBeenCalledTimes(1);
    expect(createRoot).toHaveBeenCalledWith(document.getElementById("root"));
    expect(render).toHaveBeenCalledTimes(1);
  });
});
