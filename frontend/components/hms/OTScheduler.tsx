"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/hig/Button";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { Icon } from "@/components/hig/Icon";
import { SeverityBadge, type Severity } from "@/components/hig/SeverityBadge";
import { formatDateTime, formatTime } from "@/lib/i18n/format";
import type { OTSlot, Ward } from "@/lib/api/types";

const OT_STATUS_SEVERITY: Record<string, Severity> = {
  SCHEDULED: "NORMAL",
  IN_PROGRESS: "WATCH",
  COMPLETED: "SUCCESS",
  CANCELLED: "CRITICAL",
};

const DURATION_PRESETS = [30, 60, 90, 120];

// Matches the backend's default OT slot granularity (`ot_slot_granularity_minutes` in
// backend/config.py) — quick-pick start times are aligned to this so every option lands on a
// valid slot boundary without the user needing to know the rule.
const START_GRANULARITY_MINUTES = 30;
const START_OPTION_COUNT = 8;

function roundUpToGranularity(date: Date, minutes: number): Date {
  const stepMs = minutes * 60_000;
  return new Date(Math.ceil(date.getTime() / stepMs) * stepMs);
}

function buildStartOptions(from: Date): Date[] {
  const first = roundUpToGranularity(from, START_GRANULARITY_MINUTES);
  return Array.from(
    { length: START_OPTION_COUNT },
    (_, i) => new Date(first.getTime() + i * START_GRANULARITY_MINUTES * 60_000)
  );
}

/** True when a `[start, start+durationMinutes)` slot in `wardId` would overlap an existing,
 * non-cancelled slot — mirrors the server's overlap check (`create_ot_slot` in
 * backend/ops/hms_routes.py: same ward, status != CANCELLED, `start < end && end > start`) so
 * conflicting quick-pick options can be greyed out client-side before submit, instead of only
 * surfacing as a 409 after. */
function hasConflict(wardId: string, startMs: number, durationMinutes: number, slots: OTSlot[]): boolean {
  if (!wardId) return false;
  const endMs = startMs + durationMinutes * 60_000;
  return slots.some((s) => {
    if (s.wardId !== wardId || s.status === "CANCELLED") return false;
    const sStart = new Date(s.start).getTime();
    const sEnd = new Date(s.end).getTime();
    return startMs < sEnd && endMs > sStart;
  });
}

export function OTScheduler({
  slots,
  wards,
  onCreate,
}: {
  slots: OTSlot[];
  wards: Ward[];
  onCreate: (wardId: string, start: string, end: string) => Promise<void>;
}) {
  const { t, i18n } = useTranslation(["hms", "common"]);
  const [wardId, setWardId] = useState(wards[0]?.id ?? "");
  // Frozen at mount so the quick-pick grid doesn't silently reshuffle under the user's thumb as
  // time passes.
  const startOptions = useMemo(() => buildStartOptions(new Date()), []);
  const [startMs, setStartMs] = useState<number | null>(null);
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // `wards` arrives asynchronously (SWR) after this component's first render, so the useState
  // initializer above sees an empty array — sync the default once real data shows up.
  useEffect(() => {
    if (!wardId && wards[0]) setWardId(wards[0].id);
  }, [wardId, wards]);

  const selectedConflicts = startMs !== null && hasConflict(wardId, startMs, durationMinutes, slots);

  async function submit() {
    setError(null);
    if (!wardId || startMs === null) {
      setError(t("chooseWardAndStart"));
      return;
    }
    if (hasConflict(wardId, startMs, durationMinutes, slots)) {
      setError(t("slotOverlapsPickAnother"));
      return;
    }
    const startDate = new Date(startMs);
    const endDate = new Date(startMs + durationMinutes * 60_000);
    setSubmitting(true);
    try {
      await onCreate(wardId, startDate.toISOString(), endDate.toISOString());
      setStartMs(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("couldNotScheduleSlot"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ListGroup title={t("otSlots")}>
        {slots.length === 0 && (
          <div className="px-4 py-3 flex items-center gap-2 text-body text-label-secondary">
            <Icon name="checkCircle" className="w-4.5 h-4.5" />
            {t("noSlotsScheduled")}
          </div>
        )}
        {slots.map((s) => (
          <ListRow
            key={s.id}
            label={
              <span>
                {formatDateTime(s.start, i18n.language)} – {formatTime(s.end, i18n.language)}
              </span>
            }
            value={
              <SeverityBadge
                severity={OT_STATUS_SEVERITY[s.status] ?? "NEUTRAL"}
                label={t(`common:status.${s.status}`)}
              />
            }
          />
        ))}
      </ListGroup>

      <div className="flex flex-col gap-4 bg-bg rounded-hig border border-separator shadow-card p-4">
        {wards.length > 1 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-footnote text-label-secondary">{t("ward")}</span>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {wards.map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => setWardId(w.id)}
                  className={`transition-hig text-subhead rounded-hig px-3 min-h-[2.375rem] border ${
                    wardId === w.id
                      ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                      : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
                  }`}
                >
                  {w.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">{t("startTime")}</span>
          <div className="grid grid-cols-4 gap-2">
            {startOptions.map((d) => {
              const ms = d.getTime();
              const selected = startMs === ms;
              const blocked = hasConflict(wardId, ms, durationMinutes, slots);
              return (
                <button
                  key={ms}
                  type="button"
                  disabled={blocked}
                  onClick={() => setStartMs(ms)}
                  title={blocked ? t("overlapsExistingSlot") : undefined}
                  className={`transition-hig text-caption1 rounded-hig px-1 min-h-[2.375rem] border ${
                    blocked
                      ? "bg-fill-thin text-label-tertiary border-separator opacity-50 cursor-not-allowed"
                      : selected
                      ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                      : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
                  }`}
                >
                  {formatTime(d, i18n.language)}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">{t("duration")}</span>
          <div className="grid grid-cols-4 gap-2">
            {DURATION_PRESETS.map((mins) => {
              const selected = durationMinutes === mins;
              const blocked = startMs !== null && hasConflict(wardId, startMs, mins, slots);
              return (
                <button
                  key={mins}
                  type="button"
                  disabled={blocked}
                  onClick={() => setDurationMinutes(mins)}
                  title={blocked ? t("overlapsExistingSlot") : undefined}
                  className={`transition-hig text-subhead rounded-hig min-h-[2.375rem] border ${
                    blocked
                      ? "bg-fill-thin text-label-tertiary border-separator opacity-50 cursor-not-allowed"
                      : selected
                      ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                      : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
                  }`}
                >
                  {t("minutesShort", { n: mins })}
                </button>
              );
            })}
          </div>
        </div>

        <Button type="button" onClick={submit} disabled={submitting || startMs === null || selectedConflicts}>
          {t("scheduleSlot")}
        </Button>
        {selectedConflicts && !error && (
          <p className="text-footnote text-tint-red animate-fade-in-up">{t("conflictPickAnother")}</p>
        )}
        {error && <p className="text-footnote text-tint-red animate-fade-in-up">{error}</p>}
      </div>
    </div>
  );
}
