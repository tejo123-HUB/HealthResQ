"use client";

import type { ReactNode } from "react";
import { useAdaptiveEffects } from "@/lib/theme/PerfProvider";

/** Full-screen background wrapper for brand moments (login page). On a device that can sustain
 * it (`glassEnabled`), a soft aurora-gradient wash sits behind a `--fill-thick` glass layer,
 * blurred with the rest of the page — a one-time brand moment before the flat, glass-free
 * dashboard chrome takes over. Falls back to the original flat `--bg` fill (no gradient, no
 * blur) when the perf-adaptive hook says the device can't sustain it smoothly, consistent with
 * every other glass surface in the app (Nav, ConfirmSheet). */
export function BrandBackdrop({ children }: { children: ReactNode }) {
  const { glassEnabled } = useAdaptiveEffects();

  if (!glassEnabled) {
    return <div className="relative min-h-screen bg-bg">{children}</div>;
  }

  return (
    <div className="relative min-h-screen bg-bg overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <div className="absolute -top-24 -left-24 w-[26rem] h-[26rem] rounded-full bg-tint-blue-wash blur-3xl" />
        <div className="absolute top-1/3 -right-24 w-[24rem] h-[24rem] rounded-full bg-brand-teal-wash blur-3xl" />
        <div className="absolute -bottom-24 left-1/4 w-[22rem] h-[22rem] rounded-full bg-tint-pink-wash blur-3xl" />
        <div className="absolute inset-0 backdrop-blur-2xl bg-fill-thick" />
      </div>
      {children}
    </div>
  );
}
