"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Keying on the pathname forces a remount on route change, which re-triggers the CSS entrance
 * animation — a lightweight route-transition effect with no extra dependency (framer-motion,
 * the View Transitions API's still-uneven support/timing quirks with React's async commit,
 * etc.) and no risk of animating stale content from the previous page. `materialize` (fade +
 * slight scale + a quick blur settle) reads as a new screen "resolving into focus" rather than
 * just sliding up — a small but deliberate step up from a plain fade for a page that's meant to
 * feel like a considered surface, not a bare document. */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="animate-materialize">
      {children}
    </div>
  );
}
