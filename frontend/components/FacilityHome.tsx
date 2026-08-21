"use client";

import useSWR from "swr";
import { StatCard } from "@/components/hig/Card";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { InstructionList } from "@/components/InstructionList";
import { InboxPanel } from "@/components/mailbox/InboxPanel";
import { ops } from "@/lib/api/ops";
import type { InstructionStatus } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthContext";

/** OPS-06: today's footfall/beds/staff/low-stock summary plus the instruction inbox, sourced
 * exclusively from this facility's own mailbox (via InboxPanel) and its own instructions
 * (InstructionList) — never another facility's. The "Overview" tab of the facility's single
 * workspace page. */
export function FacilityHome() {
  const { facility } = useAuth();
  const facilityId = facility!.id;

  const { data: footfall, isLoading: footfallLoading, error: footfallError } = useSWR(["footfall", facilityId], () =>
    ops.getFootfall(facilityId)
  );
  // A 404 here means "no capacity submitted yet", a legitimate empty state (OPS-06 read path) —
  // not a fetch failure, so it's swallowed rather than surfaced as an error.
  const { data: capacity, isLoading: capacityLoading } = useSWR(["capacity", facilityId], () =>
    ops.getCapacity(facilityId).catch(() => null)
  );
  const { data: inventory, isLoading: inventoryLoading, error: inventoryError } = useSWR(
    ["inventory", facilityId],
    () => ops.getInventory(facilityId)
  );
  const {
    data: instructions,
    isLoading: instructionsLoading,
    error: instructionsError,
    mutate: mutateInstructions,
  } = useSWR(["instructions", facilityId], () => ops.getInstructions(facilityId));

  const opdVisits = (footfall ?? []).reduce((sum, f) => sum + f.opdVisits, 0);
  const lowStockCount = (inventory ?? []).filter((line) => line.currentStock < 100).length;
  const statsFailed = footfallError || inventoryError;

  return (
    <div className="flex flex-col gap-6">
      {statsFailed && <ErrorBanner message="Couldn't load today's summary." />}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard icon="chart" label="OPD visits today" value={opdVisits} loading={footfallLoading} index={0} />
        <StatCard
          icon="bed"
          label="Beds occupied"
          value={capacity ? `${capacity.beds.occupied}/${capacity.beds.total}` : "—"}
          loading={capacityLoading}
          index={1}
        />
        <StatCard
          icon="checkCircle"
          label="Staff present"
          value={capacity ? capacity.staff.reduce((s, r) => s + r.present, 0) : "—"}
          loading={capacityLoading}
          index={2}
        />
        <StatCard
          icon="alert"
          label="Low-stock products"
          value={lowStockCount}
          tone={lowStockCount > 0 ? "warning" : "default"}
          loading={inventoryLoading}
          index={3}
        />
      </div>

      <InboxPanel unitId={facilityId} />

      {instructionsError ? (
        <ErrorBanner message="Couldn't load instructions." />
      ) : (
        <InstructionList
          instructions={instructions ?? []}
          loading={instructionsLoading}
          onAdvance={async (instruction, next: InstructionStatus) => {
            await ops.updateInstructionStatus(instruction.id, next);
            mutateInstructions();
          }}
        />
      )}
    </div>
  );
}
