"use client";

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { Icon } from "@/components/hig/Icon";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import type { Admission, Bed } from "@/lib/api/types";

type Filter = "ALL" | "OCCUPIED" | "AVAILABLE";

/** Occupied beds render a neutral filled tone, available beds a neutral empty tone (`--occ-filled`
 * / `--occ-empty` — plain occupancy state, not a risk signal, so it no longer borrows the
 * CRITICAL/SUCCESS severity tokens), ~12px corners — per the brief's HIG component language for
 * HMS. Tapping a bed opens a one-question confirm sheet before admitting or discharging — a
 * forgiving safety net against a mis-tap changing a real patient's status. */
export function BedGrid({
  beds,
  admissionByBedId,
  onAdmit,
  onDischarge,
}: {
  beds: Bed[];
  admissionByBedId: Map<string, Admission>;
  onAdmit: (bed: Bed) => void;
  onDischarge: (admission: Admission) => void;
}) {
  const { t } = useTranslation("hms");
  const [filter, setFilter] = useState<Filter>("ALL");
  const [pendingBed, setPendingBed] = useState<Bed | null>(null);

  const visible = useMemo(() => {
    if (filter === "OCCUPIED") return beds.filter((b) => b.occupied);
    if (filter === "AVAILABLE") return beds.filter((b) => !b.occupied);
    return beds;
  }, [beds, filter]);

  function confirm() {
    if (!pendingBed) return;
    if (pendingBed.occupied) {
      const admission = admissionByBedId.get(pendingBed.id);
      if (admission) onDischarge(admission);
    } else {
      onAdmit(pendingBed);
    }
    setPendingBed(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <SegmentedControl
        value={filter}
        onChange={setFilter}
        options={[
          { value: "ALL", label: t("filterAll") },
          { value: "OCCUPIED", label: t("filterOccupied") },
          { value: "AVAILABLE", label: t("filterAvailable") },
        ]}
      />
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
        {visible.map((bed, i) => {
          const admission = admissionByBedId.get(bed.id);
          const disabled = bed.occupied && !admission;
          return (
            <button
              key={bed.id}
              onClick={() => setPendingBed(bed)}
              disabled={disabled}
              style={{ animationDelay: `${i * 30}ms` }}
              className={`transition-hig rounded-hig aspect-square flex flex-col items-center justify-center gap-1 min-h-[4.75rem] animate-fade-in-up ${
                bed.occupied
                  ? "bg-occ-filled-wash text-occ-filled hover:brightness-95"
                  : "bg-occ-empty-wash text-occ-empty hover:brightness-95 active:opacity-70 active:scale-95"
              } ${disabled ? "opacity-50 cursor-not-allowed" : "hover:-translate-y-0.5 hover:shadow-card"}`}
            >
              <Icon name="bed" className="w-7 h-7" />
              <span className="text-subhead font-semibold">{bed.code}</span>
              <span className="text-caption1">{bed.occupied ? t("occupied") : t("free")}</span>
            </button>
          );
        })}
      </div>

      <ConfirmSheet
        open={pendingBed !== null}
        icon={pendingBed?.occupied ? "signOut" : "bed"}
        destructive={pendingBed?.occupied}
        title={
          pendingBed?.occupied
            ? t("dischargeTitle", { code: pendingBed?.code })
            : t("admitTitle", { code: pendingBed?.code })
        }
        message={pendingBed?.occupied ? t("dischargeMessage") : t("admitMessage")}
        confirmLabel={pendingBed?.occupied ? t("discharge") : t("admit")}
        onConfirm={confirm}
        onCancel={() => setPendingBed(null)}
      />
    </div>
  );
}
