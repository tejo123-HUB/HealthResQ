import type { ReactNode } from "react";

/** Full-screen cool-white background wrapper for brand moments (login page). No decorative
 * color wash — a flat `--bg` fill, consistent with every other screen in the app. */
export function BrandBackdrop({ children }: { children: ReactNode }) {
  return <div className="relative min-h-screen bg-bg">{children}</div>;
}
