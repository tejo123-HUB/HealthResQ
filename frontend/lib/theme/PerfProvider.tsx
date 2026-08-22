"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

// Two different thresholds (not one) so the state can't flicker back and forth near a single
// boundary: a device has to get meaningfully janky before glass turns off, and meaningfully
// smooth again before it turns back on.
const BAD_FRAME_MS = 42; // sustained ~24fps or worse -> fall back
const GOOD_FRAME_MS = 20; // sustained ~50fps or better -> safe to re-enable
const EMA_ALPHA = 0.1;

const AdaptiveEffectsContext = createContext<{ glassEnabled: boolean } | null>(null);

/** Runtime performance-feedback loop backing global principle #2: glass/blur is the default
 * premium visual language app-wide, gated by an automatic fallback to a flat/layered-token look
 * when a device can't sustain it smoothly. Tracks an exponential moving average of
 * requestAnimationFrame deltas (smooths out one-off hitches) rather than reacting to a single
 * slow frame. */
export function PerfProvider({ children }: { children: ReactNode }) {
  const [glassEnabled, setGlassEnabled] = useState(true);
  const emaRef = useRef<number | null>(null);
  const lastRef = useRef<number | null>(null);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    function tick(now: number) {
      if (lastRef.current !== null) {
        const delta = now - lastRef.current;
        emaRef.current = emaRef.current === null ? delta : emaRef.current + EMA_ALPHA * (delta - emaRef.current);
        if (emaRef.current > BAD_FRAME_MS) setGlassEnabled(false);
        else if (emaRef.current < GOOD_FRAME_MS) setGlassEnabled(true);
      }
      lastRef.current = now;
      frameRef.current = requestAnimationFrame(tick);
    }
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  return <AdaptiveEffectsContext.Provider value={{ glassEnabled }}>{children}</AdaptiveEffectsContext.Provider>;
}

export function useAdaptiveEffects() {
  const ctx = useContext(AdaptiveEffectsContext);
  if (!ctx) throw new Error("useAdaptiveEffects must be used within PerfProvider");
  return ctx;
}
