import { useTranslation } from "react-i18next";
import type { ReferralStatus } from "@/lib/api/types";

const STAGE_ORDER: ReferralStatus[] = ["OPEN", "ACKNOWLEDGED", "CLOSED"];

/** Compact inline 3-segment status track for a referral's Open -> Acknowledged -> Closed
 * lifecycle. Replaces the single `SeverityBadge` that used to sit here (OPEN mapped to WATCH,
 * ACKNOWLEDGED to NORMAL, CLOSED to SUCCESS) — a plain forward-only progression isn't a severity
 * signal, so borrowing severity color language for it was misleading. Stages already passed and
 * the current stage render filled/labeled; stages still ahead render as muted placeholders, so a
 * referral's position in its lifecycle reads at a glance. */
export function ReferralStatusTrack({ status }: { status: ReferralStatus }) {
  const { t } = useTranslation(["hms", "common"]);
  const stages = STAGE_ORDER.map((s) => ({ status: s, label: t(`common:status.${s}`) }));
  const currentIndex = stages.findIndex((s) => s.status === status);

  return (
    <div
      className="flex items-center"
      role="img"
      aria-label={t("hms:referralStatusLabel", { status: stages[currentIndex]?.label ?? status })}
    >
      {stages.map((stage, i) => {
        const done = currentIndex >= 0 && i < currentIndex;
        const current = i === currentIndex;
        return (
          <div key={stage.status} className="flex items-center">
            {i > 0 && (
              <span
                aria-hidden="true"
                className={`block w-2.5 h-px shrink-0 transition-hig ${
                  done || current ? "bg-tint-blue" : "bg-separator"
                }`}
              />
            )}
            <span
              className={`text-caption2 font-semibold rounded-full px-2 py-0.5 whitespace-nowrap transition-hig ${
                current
                  ? "bg-tint-blue text-white"
                  : done
                  ? "bg-tint-blue-wash text-tint-blue"
                  : "bg-fill-thin text-label-tertiary"
              }`}
            >
              {stage.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
