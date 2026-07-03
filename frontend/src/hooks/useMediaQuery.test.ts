import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useMediaQuery } from "./useMediaQuery";

type ChangeListener = () => void;

/** Build a controllable matchMedia stub and track the registered change listener. */
function installMatchMedia(initialMatches: boolean) {
  const listeners: ChangeListener[] = [];
  const mql = {
    matches: initialMatches,
    addEventListener: vi.fn((_type: string, cb: ChangeListener) => {
      listeners.push(cb);
    }),
    removeEventListener: vi.fn((_type: string, cb: ChangeListener) => {
      const idx = listeners.indexOf(cb);
      if (idx >= 0) listeners.splice(idx, 1);
    }),
  };
  const matchMedia = vi.fn(() => mql);
  Object.defineProperty(window, "matchMedia", {
    value: matchMedia,
    configurable: true,
    writable: true,
  });
  return {
    matchMedia,
    mql,
    fireChange(next: boolean) {
      mql.matches = next;
      act(() => {
        for (const cb of [...listeners]) cb();
      });
    },
    listenerCount: () => listeners.length,
  };
}

const originalMatchMedia = window.matchMedia;

afterEach(() => {
  Object.defineProperty(window, "matchMedia", {
    value: originalMatchMedia,
    configurable: true,
    writable: true,
  });
  vi.restoreAllMocks();
});

describe("useMediaQuery", () => {
  it("returns the initial match state from matchMedia", () => {
    const env = installMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));

    expect(result.current).toBe(true);
    expect(env.matchMedia).toHaveBeenCalledWith("(min-width: 768px)");
    expect(env.mql.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("returns false when the query does not match initially", () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));

    expect(result.current).toBe(false);
  });

  it("updates when the media query change event fires", () => {
    const env = installMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));
    expect(result.current).toBe(false);

    env.fireChange(true);
    expect(result.current).toBe(true);

    env.fireChange(false);
    expect(result.current).toBe(false);
  });

  it("removes the change listener on unmount", () => {
    const env = installMatchMedia(true);
    const { unmount } = renderHook(() => useMediaQuery("(min-width: 768px)"));
    expect(env.listenerCount()).toBe(1);

    unmount();
    expect(env.mql.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
    expect(env.listenerCount()).toBe(0);
  });

  it("re-subscribes when the query changes", () => {
    const env = installMatchMedia(true);
    const { rerender } = renderHook(({ q }) => useMediaQuery(q), {
      initialProps: { q: "(min-width: 768px)" },
    });

    rerender({ q: "(min-width: 1024px)" });
    expect(env.matchMedia).toHaveBeenCalledWith("(min-width: 1024px)");
    expect(env.mql.removeEventListener).toHaveBeenCalled();
  });

  it("returns false and skips subscribing when matchMedia is unavailable", () => {
    Object.defineProperty(window, "matchMedia", {
      value: undefined,
      configurable: true,
      writable: true,
    });

    const { result } = renderHook(() => useMediaQuery("(min-width: 768px)"));
    expect(result.current).toBe(false);
  });
});
