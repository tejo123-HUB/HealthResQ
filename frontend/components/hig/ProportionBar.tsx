// Thin length-encoded bar — a proportional visual complement to a raw count, so a severity
// breakdown (or any value/max comparison) reads at a glance without doing mental math on the
// numbers alone. Presentational only: callers own the color via `className`.

import { useTranslation } from "react-i18next";

/** `value`/`max` render as a filled-width bar (`value / max` clamped to [0, 1]). Pass a `tone`
 * className (e.g. `bg-tint-red`) to color the fill; the track behind it always uses a neutral
 * fill token so the bar reads the same regardless of tone. */
export function ProportionBar({
  value,
  max,
  className = "",
  trackClassName = "",
}: {
  value: number;
  max: number;
  /** Fill color class, e.g. `bg-tint-red`. Defaults to a neutral fill. */
  className?: string;
  trackClassName?: string;
}) {
  const { t } = useTranslation("dashboard");
  const ratio = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return (
    <div
      className={`h-1 w-full rounded-full bg-fill-regular overflow-hidden ${trackClassName}`}
      role="img"
      aria-label={t("dashboard:proportionOf", { value, max })}
    >
      <div
        className={`h-full rounded-full transition-hig ${className || "bg-label-tertiary"}`}
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  );
}
