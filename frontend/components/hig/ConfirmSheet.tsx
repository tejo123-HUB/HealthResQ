"use client";

import { useEffect, useRef } from "react";
import { Icon } from "@/components/hig/Icon";
import { SheetShell } from "@/components/hig/Sheet";

/** HIG action-sheet-style confirmation, used before any tap that changes real-world state in one
 * step (admit/discharge a bed, approve/reject a recommendation) — a forgiving safety net for a
 * user who taps fast and doesn't read dense text: one big question, two big buttons, nothing
 * else. Glass material backdrop per the brief's §2.3 material tokens. */
export function ConfirmSheet({
  open,
  icon,
  title,
  message,
  confirmLabel,
  destructive = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  icon: Parameters<typeof Icon>[0]["name"];
  title: string;
  message?: string;
  confirmLabel: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  // Escape to back out, same as tapping the backdrop — and focus starts on Cancel, not Confirm,
  // so a keyboard user who just hits Enter out of habit doesn't accidentally commit a
  // consequential action (admit/discharge/approve) they only meant to dismiss.
  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <SheetShell open={open} onDismiss={onCancel}>
      <div
        className={`w-14 h-14 rounded-full flex items-center justify-center mb-1 animate-pop-in ${
          destructive ? "bg-tint-red-wash text-tint-red" : "bg-tint-blue-wash text-tint-blue"
        }`}
      >
        <Icon name={icon} className="w-7 h-7" />
      </div>
      <p className="text-headline">{title}</p>
      {message && <p className="text-body text-label-secondary">{message}</p>}
      <div className="flex flex-col gap-2 w-full mt-4">
        <button
          onClick={onConfirm}
          className={`transition-hig text-headline rounded-hig min-h-[2.75rem] text-white active:opacity-70 active:scale-[0.97] hover:shadow-card-hover ${
            destructive
              ? "bg-tint-red hover:bg-[color-mix(in_srgb,var(--tint-red)_88%,black)]"
              : "bg-tint-blue hover:bg-[color-mix(in_srgb,var(--tint-blue)_88%,black)]"
          }`}
        >
          {confirmLabel}
        </button>
        <button
          ref={cancelRef}
          onClick={onCancel}
          className="transition-hig text-headline rounded-hig min-h-[2.75rem] bg-fill-regular text-label hover:bg-fill-thick active:opacity-70 active:scale-[0.97] focus:outline-none focus:ring-2 focus:ring-tint-blue-wash"
        >
          Cancel
        </button>
      </div>
    </SheetShell>
  );
}
