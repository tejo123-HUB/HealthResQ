"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/** Keying on the pathname forces a remount on route change, which re-triggers the CSS entrance
 * animation — a lightweight route-transition effect with no extra dependency (framer-motion,
 * view-transitions polyfill, etc.) and no risk of animating stale content from the previous page. */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="animate-fade-in-up">
      {children}
    </div>
  );
}
