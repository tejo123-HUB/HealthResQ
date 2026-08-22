"use client";

import { Icon } from "@/components/hig/Icon";

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
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onCancel} />
      <div className="relative w-full sm:max-w-sm bg-fill-thick backdrop-blur-xl rounded-t-2xl sm:rounded-hig border border-separator shadow-popover p-6 flex flex-col items-center gap-2 text-center animate-sheet-up sm:animate-scale-in">
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
            onClick={onCancel}
            className="transition-hig text-headline rounded-hig min-h-[2.75rem] bg-fill-regular text-label hover:bg-fill-thick active:opacity-70 active:scale-[0.97]"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
