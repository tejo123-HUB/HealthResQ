"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Icon } from "@/components/hig/Icon";

type ToastKind = "success" | "error" | "info";
type ToastItem = { id: number; kind: ToastKind; message: string; leaving?: boolean };

type ToastApi = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

const KIND_STYLE: Record<ToastKind, { icon: Parameters<typeof Icon>[0]["name"]; classes: string }> = {
  success: { icon: "checkCircle", classes: "bg-tint-green-wash text-tint-green" },
  error: { icon: "alert", classes: "bg-tint-red-wash text-tint-red" },
  info: { icon: "flag", classes: "bg-tint-blue-wash text-tint-blue" },
};

const AUTO_DISMISS_MS = 4000;
const EXIT_ANIMATION_MS = 220;

/** Every mutating action in this app (admit, discharge, approve, dispatch…) used to only ever
 * show its result via a silent SWR re-render — real, but invisible unless you were staring at
 * the exact number that changed. A toast makes "that worked" (or didn't) a first-class, glanceable
 * event, the same way a native app confirms a background action without blocking on it. Mounted
 * once at the root layout so any screen can call `useToast()` without prop-drilling a handler
 * down through every form. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => {
    // Two-phase removal: flip to "leaving" so the exit keyframe plays, then actually drop it from
    // the array once that animation has had time to finish — an instant unmount would just pop
    // the toast out of existence with no visual acknowledgement that it's gone.
    setItems((cur) => cur.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), EXIT_ANIMATION_MS);
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setItems((cur) => [...cur, { id, kind, message }]);
      setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
    },
    [dismiss]
  );

  const api: ToastApi = {
    success: (message) => push("success", message),
    error: (message) => push("error", message),
    info: (message) => push("info", message),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed inset-x-0 top-0 sm:top-4 sm:inset-x-auto sm:right-4 z-[100] flex flex-col items-center sm:items-end gap-2 px-4 py-4 sm:p-0 pointer-events-none">
        {items.map((t) => {
          const style = KIND_STYLE[t.kind];
          return (
            <div
              key={t.id}
              onClick={() => dismiss(t.id)}
              className={`pointer-events-auto cursor-pointer flex items-center gap-2.5 bg-fill-thick backdrop-blur-xl border border-separator shadow-popover rounded-hig px-4 py-3 max-w-sm w-full sm:w-auto ${
                t.leaving ? "animate-toast-out" : "animate-toast-in"
              }`}
            >
              <span className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${style.classes}`}>
                <Icon
                  name={style.icon}
                  className={`w-4 h-4 ${t.kind === "success" ? "[stroke-dasharray:65] animate-draw-check" : "animate-pop-in"}`}
                />
              </span>
              <p className="text-body text-label flex-1">{t.message}</p>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
