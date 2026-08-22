"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/hig/Button";
import { ListGroup } from "@/components/hig/Card";
import { Icon } from "@/components/hig/Icon";
import { ReferralStatusTrack } from "@/components/hms/ReferralStatusTrack";
import type { Facility, Referral, ReferralUrgency } from "@/lib/api/types";

export function ReferralTracker({
  referrals,
  facilityId,
  destinationOptions,
  onCreate,
  onAdvanceStatus,
}: {
  referrals: Referral[];
  facilityId: string;
  destinationOptions: Facility[];
  onCreate: (destFacilityId: string, reason: string, urgency: ReferralUrgency) => Promise<void>;
  onAdvanceStatus: (referral: Referral) => Promise<void>;
}) {
  const { t } = useTranslation(["hms", "common"]);
  const [destFacilityId, setDestFacilityId] = useState(destinationOptions[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [urgency, setUrgency] = useState<ReferralUrgency>("ROUTINE");
  const [error, setError] = useState<string | null>(null);

  // `destinationOptions` arrives asynchronously (SWR) after this component's first render, so
  // the useState initializer above sees an empty array — sync the default once real data shows up.
  useEffect(() => {
    if (!destFacilityId && destinationOptions[0]) setDestFacilityId(destinationOptions[0].id);
  }, [destFacilityId, destinationOptions]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!destFacilityId || !reason.trim()) {
      setError(t("hms:chooseDestinationAndReason"));
      return;
    }
    try {
      await onCreate(destFacilityId, reason.trim(), urgency);
      setReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("hms:couldNotCreateReferral"));
    }
  }

  const nextStatus = (status: string): "ACKNOWLEDGED" | "CLOSED" | null =>
    status === "OPEN" ? "ACKNOWLEDGED" : status === "ACKNOWLEDGED" ? "CLOSED" : null;

  return (
    <div className="flex flex-col gap-4">
      <ListGroup title={t("hms:referralsHeading")}>
        {referrals.length === 0 && (
          <div className="px-4 py-3 flex items-center gap-2 text-body text-label-secondary">
            <Icon name="checkCircle" className="w-4.5 h-4.5" />
            {t("hms:noReferrals")}
          </div>
        )}
        {referrals.map((r, idx) => {
          const next = nextStatus(r.status);
          const outgoing = r.sourceFacilityId === facilityId;
          return (
            <div
              key={r.id}
              style={{ animationDelay: `${idx * 40}ms` }}
              className="px-4 py-3 flex items-center justify-between gap-3 animate-fade-in-up hover:bg-fill-thin transition-hig"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-full bg-fill-regular flex items-center justify-center shrink-0 text-label-secondary">
                  <Icon name={outgoing ? "chevronRight" : "inbox"} className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-body truncate" title={r.reason}>
                    {r.reason}
                  </p>
                  <p className="text-footnote text-label-secondary">
                    {outgoing ? t("hms:outgoing") : t("hms:incoming")} · {t(`common:urgency.${r.urgency}`)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <ReferralStatusTrack status={r.status} />
                {next && (
                  <Button variant="secondary" onClick={() => onAdvanceStatus(r)}>
                    {t("hms:markStatus", { status: t(`common:status.${next}`) })}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </ListGroup>

      <form onSubmit={onSubmit} className="flex flex-col gap-4 bg-bg rounded-hig border border-separator shadow-card p-4">
        <div className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">{t("hms:referTo")}</span>
          <div className="flex gap-2 flex-wrap">
            {destinationOptions.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setDestFacilityId(f.id)}
                className={`transition-hig text-subhead rounded-hig px-4 min-h-[2.375rem] border ${
                  destFacilityId === f.id
                    ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                    : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
                }`}
              >
                {f.name}
              </button>
            ))}
          </div>
        </div>
        <label className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">{t("hms:reason")}</span>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("hms:reasonPlaceholder")}
            className="text-body bg-bg-secondary rounded-hig px-3 min-h-[2.375rem] border border-separator outline-none transition-hig focus:border-tint-blue focus:ring-2 focus:ring-tint-blue-wash"
          />
        </label>
        <div className="flex flex-col gap-1.5">
          <span className="text-footnote text-label-secondary">{t("hms:urgency")}</span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setUrgency("ROUTINE")}
              className={`transition-hig text-subhead rounded-hig flex-1 min-h-[2.375rem] border ${
                urgency === "ROUTINE"
                  ? "bg-tint-blue-wash text-tint-blue border-tint-blue"
                  : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
              }`}
            >
              {t("common:urgency.ROUTINE")}
            </button>
            <button
              type="button"
              onClick={() => setUrgency("URGENT")}
              className={`transition-hig text-subhead rounded-hig flex-1 min-h-[2.375rem] border ${
                urgency === "URGENT"
                  ? "bg-tint-red-wash text-tint-red border-tint-red"
                  : "bg-bg-secondary text-label border-separator hover:bg-fill-thin"
              }`}
            >
              {t("common:urgency.URGENT")}
            </button>
          </div>
        </div>
        <Button type="submit">{t("hms:refer")}</Button>
        {error && <p className="text-footnote text-tint-red animate-fade-in-up">{error}</p>}
      </form>
    </div>
  );
}
