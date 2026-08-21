"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/hig/Button";
import { ListGroup, ListRow } from "@/components/hig/Card";
import { SeverityBadge, type Severity } from "@/components/hig/SeverityBadge";
import type { OTSlot, Ward } from "@/lib/api/types";

const OT_STATUS_SEVERITY: Record<string, Severity> = {
  SCHEDULED: "NORMAL",
  IN_PROGRESS: "WATCH",
  COMPLETED: "SUCCESS",
  CANCELLED: "CRITICAL",
};

const DURATION_PRESETS = [30, 60, 90, 120];

export function OTScheduler({
  slots,
  wards,
  onCreate,
}: {
  slots: OTSlot[];
  wards: Ward[];
  onCreate: (wardId: string, start: string, end: string) => Promise<void>;
}) {
  const [wardId, setWardId] = useState(wards[0]?.id ?? "");
  const [start, setStart] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [error, setError] = useState<string | null>(null);

  // `wards` arrives asynchronously (SWR) after this component's first render, so the useState
  // initializer above sees an empty array — sync the default once real data shows up.
  useEffect(() => {
    if (!wardId && wards[0]) setWardId(wards[0].id);
  }, [wardId, wards]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!wardId || !start) {
      setError("Choose a ward and start time");
      return;
    }
    const startDate = new Date(start);
    const endDate = new Date(startDate.getTime() + durationMinutes * 60_000);
    try {
      await onCreate(wardId, startDate.toISOString(), endDate.toISOString());
      setStart("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not schedule slot");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ListGroup title="OT slots">
        {slots.length === 0 && <div className="px-4 py-3 text-body text-label-secondary">No slots scheduled.</div>}
        {slots.map((s) => (
          <ListRow
            key={s.id}
            label={
              <span>
                {new Date(s.start).toLocaleString()} – {new Date(s.end).toLocaleTimeString()}
              </span>
            }
            value={<SeverityBadge severity={OT_STATUS_SEVERITY[s.status] ?? "NEUTRAL"} label={s.status} />}
          />
        ))}
      </ListGroup>

      <form onSubmit={onSubmit} className="flex flex-col gap-4 bg-bg rounded-hig border border-separator shadow-card p-4">
        {wards.length > 1 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-footnote text-label-secondary">Ward</span>
            <div className="flex gap-2 flex-wrap">
              {wards.map((w) => (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => setWardId(w.id)}
                  className={`transition-hig text-subhead rounded-hig px-4 min-h-[44px] border ${
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
        <label className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">Start time</span>
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="text-body bg-bg-secondary rounded-hig px-3 min-h-[44px] border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
          />
        </label>
        <div className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">Duration</span>
          <div className="flex gap-2">
            {DURATION_PRESETS.map((mins) => (
              <button
                key={mins}
                type="button"
                onClick={() => setDurationMinutes(mins)}
                className={`transition-hig text-subhead rounded-hig flex-1 min-h-[44px] border ${
                  durationMinutes === mins
                    ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                    : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
                }`}
              >
                {mins} min
              </button>
            ))}
          </div>
        </div>
        <Button type="submit">Schedule slot</Button>
        {error && <p className="text-footnote text-tint-red animate-fade-in-up">{error}</p>}
      </form>
    </div>
  );
}
