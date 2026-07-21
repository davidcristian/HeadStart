import "@testing-library/jest-dom";
import { vi } from "vitest";

vi.mock("virtual:pwa-register", () => ({
  registerSW: () => () => {},
}));

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Provide a deterministic in-memory localStorage for tests. jsdom's storage can
// be shadowed by Node's experimental built-in localStorage, so we install our
// own simple implementation when one is not usable.
function installLocalStorage(): void {
  let usable: boolean;
  try {
    usable = typeof localStorage !== "undefined" && localStorage !== null;
    if (usable) localStorage.getItem("__probe__");
  } catch {
    usable = false;
  }
  if (usable) return;

  const store = new Map<string, string>();
  const mock: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key) => (store.has(key) ? store.get(key)! : null),
    key: (index) => Array.from(store.keys())[index] ?? null,
    removeItem: (key) => void store.delete(key),
    setItem: (key, value) => void store.set(key, String(value)),
  };
  Object.defineProperty(globalThis, "localStorage", { value: mock, configurable: true });
}

installLocalStorage();
