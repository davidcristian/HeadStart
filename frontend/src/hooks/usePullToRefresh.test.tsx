import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePullToRefresh } from "./usePullToRefresh";

/** Dispatch a synthetic touch event with a controllable clientY. */
function dispatchTouch(type: "touchstart" | "touchmove" | "touchend", clientY?: number) {
  const event = new Event(type) as unknown as {
    type: string;
    touches: Array<{ clientY: number }>;
  };
  event.touches = clientY === undefined ? [] : [{ clientY }];
  act(() => {
    window.dispatchEvent(event as unknown as Event);
  });
}

function setScrollY(value: number) {
  Object.defineProperty(window, "scrollY", { value, configurable: true, writable: true });
}

afterEach(() => {
  setScrollY(0);
  vi.restoreAllMocks();
});

describe("usePullToRefresh", () => {
  it("does not attach listeners when disabled", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    const onRefresh = vi.fn();
    const { result } = renderHook(() => usePullToRefresh(onRefresh, false));

    const touchAdds = addSpy.mock.calls.filter(([name]) => String(name).startsWith("touch"));
    expect(touchAdds).toHaveLength(0);
    expect(result.current).toEqual({ pulling: false, refreshing: false });
  });

  it("triggers refresh after pulling past the threshold", async () => {
    let resolveRefresh: () => void = () => {};
    const onRefresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart", 10);
    expect(result.current.pulling).toBe(false);

    dispatchTouch("touchmove", 100); // delta 90 >= 72
    expect(result.current.pulling).toBe(true);

    await act(async () => {
      dispatchTouch("touchend");
    });
    expect(onRefresh).toHaveBeenCalledTimes(1);
    expect(result.current.pulling).toBe(false);
    expect(result.current.refreshing).toBe(true);

    await act(async () => {
      resolveRefresh();
      await Promise.resolve();
    });
    expect(result.current.refreshing).toBe(false);
  });

  it("does not refresh when the pull is below the threshold", async () => {
    const onRefresh = vi.fn(async () => {});
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 50); // delta 40 < 72
    expect(result.current.pulling).toBe(false);

    await act(async () => {
      dispatchTouch("touchend");
    });
    expect(onRefresh).not.toHaveBeenCalled();
    expect(result.current.pulling).toBe(false);
    expect(result.current.refreshing).toBe(false);
  });

  it("ignores gestures while the page is scrolled", () => {
    const onRefresh = vi.fn(async () => {});
    setScrollY(50);
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 200); // scrollY > 0, so ignored
    expect(result.current.pulling).toBe(false);
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("handles missing touch points by defaulting clientY to zero", () => {
    const onRefresh = vi.fn(async () => {});
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart"); // no touches -> startY 0
    dispatchTouch("touchmove"); // no touches -> delta 0 < threshold
    expect(result.current.pulling).toBe(false);
  });

  it("ignores a second gesture while a refresh is in flight", async () => {
    let resolveRefresh: () => void = () => {};
    const onRefresh = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveRefresh = resolve;
        }),
    );
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 100);
    await act(async () => {
      dispatchTouch("touchend");
    });
    expect(result.current.refreshing).toBe(true);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    // refreshingRef is true now: these should be no-ops
    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 200);
    await act(async () => {
      dispatchTouch("touchend");
    });
    expect(onRefresh).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveRefresh();
      await Promise.resolve();
    });
    expect(result.current.refreshing).toBe(false);
  });

  it("resets a ready pull that is cancelled without triggering refresh", async () => {
    const onRefresh = vi.fn(async () => {});
    const { result } = renderHook(() => usePullToRefresh(onRefresh));

    dispatchTouch("touchstart", 10);
    dispatchTouch("touchmove", 100); // ready
    expect(result.current.pulling).toBe(true);

    // A move back below threshold clears ready before end.
    dispatchTouch("touchmove", 20); // delta 10 < 72 -> not ready
    expect(result.current.pulling).toBe(false);

    await act(async () => {
      dispatchTouch("touchend");
    });
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("removes listeners on unmount and re-run", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const onRefresh = vi.fn(async () => {});
    const { unmount } = renderHook(() => usePullToRefresh(onRefresh));

    unmount();
    const touchRemoves = removeSpy.mock.calls.filter(([name]) => String(name).startsWith("touch"));
    expect(touchRemoves.length).toBeGreaterThanOrEqual(3);
  });
});
