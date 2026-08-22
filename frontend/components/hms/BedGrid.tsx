"use client";

import { useMemo, useState } from "react";
import { ConfirmSheet } from "@/components/hig/ConfirmSheet";
import { Icon } from "@/components/hig/Icon";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import type { Admission, Bed } from "@/lib/api/types";

type Filter = "ALL" | "OCCUPIED" | "AVAILABLE";

/** Occupied beds render red-tint, available beds green-tint, ~12px corners — per the brief's HIG
 * component language for HMS. Tapping a bed opens a one-question confirm sheet before admitting
 * or discharging — a forgiving safety net against a mis-tap changing a real patient's status. */
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
          { value: "ALL", label: "All" },
          { value: "OCCUPIED", label: "Occupied" },
          { value: "AVAILABLE", label: "Available" },
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
                  ? "bg-tint-red-wash text-tint-red hover:bg-tint-red-wash-strong"
                  : "bg-tint-green-wash text-tint-green hover:brightness-95 active:opacity-70 active:scale-95"
              } ${disabled ? "opacity-50 cursor-not-allowed" : "hover:-translate-y-0.5 hover:shadow-card"}`}
            >
              <Icon name="bed" className="w-7 h-7" />
              <span className="text-subhead font-semibold">{bed.code}</span>
              <span className="text-caption1">{bed.occupied ? "Occupied" : "Free"}</span>
            </button>
          );
        })}
      </div>

      <ConfirmSheet
        open={pendingBed !== null}
        icon={pendingBed?.occupied ? "signOut" : "bed"}
        destructive={pendingBed?.occupied}
        title={pendingBed?.occupied ? `Discharge ${pendingBed?.code}?` : `Admit patient into ${pendingBed?.code}?`}
        message={
          pendingBed?.occupied
            ? "This frees the bed for the next patient."
            : "The bed will be marked occupied right away."
        }
        confirmLabel={pendingBed?.occupied ? "Discharge" : "Admit"}
        onConfirm={confirm}
        onCancel={() => setPendingBed(null)}
      />
    </div>
  );
}
