"use client";

import { Icon } from "@/components/hig/Icon";

/** Surfaces a failed fetch instead of letting an empty/`?? []` fallback masquerade as "no data" —
 * every data-fetching panel that matters (facility summary, dashboard summary, warehouse stock)
 * passes its SWR `error` through here rather than swallowing it. */
export function ErrorBanner({ message = "Couldn't load this — check your connection and try again.", onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="animate-fade-in flex items-center gap-3 bg-tint-red-wash text-tint-red rounded-hig px-4 py-3">
      <Icon name="alert" className="w-4.5 h-4.5 shrink-0" />
      <p className="text-body flex-1">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="text-footnote font-semibold underline shrink-0">
          Retry
        </button>
      )}
    </div>
  );
}
