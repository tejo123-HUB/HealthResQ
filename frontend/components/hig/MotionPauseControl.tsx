"use client";

import { useTranslation } from "react-i18next";
import { Icon } from "@/components/hig/Icon";

/** WCAG 2.2.2 (Pause, Stop, Hide): any auto-playing animation running longer than 5 seconds needs
 * an explicit in-page control to stop it, on top of (not instead of) honoring
 * `prefers-reduced-motion`. Callers own the actual paused/running state; this is just the
 * standard visible affordance so every long-running animation in the app looks/behaves the same
 * way. */
export function MotionPauseControl({
  paused,
  onToggle,
  label,
  className = "",
}: {
  paused: boolean;
  onToggle: () => void;
  /** Describes what's animating (e.g. "risk map pulse") — passed untranslated by data-heavy
   * callers today; falls back to a generic translated "motion" if omitted. */
  label?: string;
  className?: string;
}) {
  const { t } = useTranslation("common");
  const resolvedLabel = label ?? t("motion");
  const description = paused ? t("resumeMotion", { label: resolvedLabel }) : t("pauseMotion", { label: resolvedLabel });
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={paused}
      aria-label={description}
      title={description}
      className={`w-8 h-8 flex items-center justify-center rounded-full bg-fill-thick backdrop-blur-xl text-label-secondary shadow-card hover:bg-fill-regular active:scale-90 transition-hig ${className}`}
    >
      <Icon name={paused ? "play" : "pause"} className="w-4 h-4" />
    </button>
  );
}
