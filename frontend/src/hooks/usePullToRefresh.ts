/** Touch pull-to-refresh for mobile job feeds. */

import { useEffect, useRef, useState } from "react";

const PULL_THRESHOLD_PX = 72;

export function usePullToRefresh(onRefresh: () => void | Promise<void>, enabled = true) {
  const [pulling, setPulling] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const onRefreshRef = useRef(onRefresh);
  const readyRef = useRef(false);
  const refreshingRef = useRef(false);

  onRefreshRef.current = onRefresh;
  refreshingRef.current = refreshing;

  useEffect(() => {
    if (!enabled) return;

    let startY = 0;

    function onTouchStart(event: TouchEvent) {
      if (window.scrollY > 0 || refreshingRef.current) return;
      startY = event.touches[0]?.clientY ?? 0;
      readyRef.current = false;
      setPulling(false);
    }

    function onTouchMove(event: TouchEvent) {
      if (window.scrollY > 0 || refreshingRef.current) return;
      const delta = (event.touches[0]?.clientY ?? 0) - startY;
      const ready = delta >= PULL_THRESHOLD_PX;
      readyRef.current = ready;
      setPulling(ready);
    }

    async function onTouchEnd() {
      if (!readyRef.current || refreshingRef.current) {
        readyRef.current = false;
        setPulling(false);
        return;
      }
      readyRef.current = false;
      setPulling(false);
      setRefreshing(true);
      try {
        await onRefreshRef.current();
      } finally {
        setRefreshing(false);
      }
    }

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: true });
    window.addEventListener("touchend", onTouchEnd);
    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [enabled]);

  return { pulling, refreshing };
}
