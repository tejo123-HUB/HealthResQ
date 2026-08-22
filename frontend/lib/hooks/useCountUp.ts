"use client";

import { useEffect, useRef, useState } from "react";

const EASE_OUT_QUINT = (t: number) => 1 - Math.pow(1 - t, 5);

/** Tweens a stat card's number from its previous value to the next one whenever it changes,
 * instead of the digit just popping in — makes a dashboard refresh read as "this number moved"
 * rather than "the page re-rendered". Skips the tween entirely on first mount (nothing to
 * animate from) and for non-finite/absent values, so loading states still just show the
 * caller's own skeleton. */
export function useCountUp(target: number | undefined, durationMs = 700): number | undefined {
  const [display, setDisplay] = useState(target);
  const prevRef = useRef(target);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (target === undefined || !Number.isFinite(target)) {
      setDisplay(target);
      prevRef.current = target;
      return;
    }
    const from = prevRef.current !== undefined && Number.isFinite(prevRef.current) ? prevRef.current : target;
    prevRef.current = target;
    if (from === target) {
      setDisplay(target);
      return;
    }

    const start = performance.now();
    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / durationMs);
      const eased = EASE_OUT_QUINT(progress);
      setDisplay(from + (target! - from) * eased);
      if (progress < 1) frameRef.current = requestAnimationFrame(tick);
    }
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return display;
}
