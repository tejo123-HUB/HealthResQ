"use client";

import type { ReactNode } from "react";
import { useAdaptiveEffects } from "@/lib/theme/PerfProvider";

/** Shared glass-backdrop sheet shell — bottom sheet on mobile, centered popover on larger screens.
 * Extracted out of ConfirmSheet so any other tap-to-pick sheet (e.g. LanguageSheet) gets the same
 * chrome/motion without re-implementing the backdrop + responsive panel positioning. Content
 * layout (padding, alignment, scroll behavior) is left to the caller via `className`, since a
 * two-button confirm and a long scrollable list want different internal layouts. */
export function SheetShell({
  open,
  onDismiss,
  children,
  className = "p-6 flex flex-col items-center gap-2 text-center",
  maxWidthClass = "sm:max-w-sm",
}: {
  open: boolean;
  onDismiss: () => void;
  children: ReactNode;
  className?: string;
  maxWidthClass?: string;
}) {
  const { glassEnabled } = useAdaptiveEffects();
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onDismiss} />
      <div
        className={`relative w-full ${maxWidthClass} bg-fill-thick rounded-t-2xl sm:rounded-hig border border-separator shadow-popover animate-sheet-up sm:animate-scale-in ${className} ${
          glassEnabled ? "backdrop-blur-xl" : ""
        }`}
      >
        {children}
      </div>
    </div>
  );
}
