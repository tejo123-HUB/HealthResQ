"use client";

import { useEffect, useState } from "react";

/** Tracks the OS-level `prefers-reduced-motion` preference live, for the JS-driven motion the
 * global CSS media query in globals.css can't reach on its own (e.g. skipping a typed/streamed
 * text effect, or deciding whether a map marker is allowed to pulse at all). Starts `false` on
 * the server/first render (matchMedia isn't available there) and settles to the real value on
 * mount — callers that gate an entrance animation should treat that first-paint `false` as
 * harmless, since the animation classes themselves are already neutralized by the CSS block. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
