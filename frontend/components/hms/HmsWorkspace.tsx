"use client";

import { useState } from "react";
import useSWR from "swr";
import { BedGrid } from "@/components/hms/BedGrid";
import { OTScheduler } from "@/components/hms/OTScheduler";
import { ReferralTracker } from "@/components/hms/ReferralTracker";
import { WardList } from "@/components/hms/WardList";
import { ErrorBanner } from "@/components/hig/ErrorBanner";
import { Skeleton } from "@/components/hig/Skeleton";
import { ops } from "@/lib/api/ops";
import type { Admission, Bed, ReferralUrgency } from "@/lib/api/types";

/** OPS-11-13, as a self-contained workspace section (not a top-level nav destination) — mounted
 * inside the facility's single workspace page as the "Hospital" tab. */
export function HmsWorkspace({ facilityId }: { facilityId: string }) {
  const [selectedWardId, setSelectedWardId] = useState<string | null>(null);

  const {
    data: wards,
    isLoading: wardsLoading,
    error: wardsError,
  } = useSWR(["wards", facilityId], () => ops.listWards(facilityId), {
    onSuccess: (w) => setSelectedWardId((cur) => cur ?? w[0]?.id ?? null),
  });
  const { data: beds, isLoading: bedsLoading, mutate: mutateBeds } = useSWR(
    selectedWardId ? ["beds", selectedWardId] : null,
    () => ops.listBeds(selectedWardId as string)
  );
  const { data: admissions, mutate: mutateAdmissions } = useSWR(
    selectedWardId ? ["admissions", selectedWardId] : null,
    () => ops.listWardAdmissions(selectedWardId as string, true)
  );
  const { data: otSlots, mutate: mutateOt } = useSWR(["ot-slots", facilityId], () => ops.listOtSlots(facilityId));
  const { data: referrals, mutate: mutateReferrals } = useSWR(["referrals", facilityId], () =>
    ops.listReferrals(facilityId)
  );
  const { data: referralCandidates } = useSWR(["referral-candidates", facilityId], () =>
    ops.listReferralCandidates(facilityId)
  );

  const admissionByBedId = new Map<string, Admission>((admissions ?? []).map((a) => [a.bedId, a]));

  async function admit(bed: Bed) {
    if (!selectedWardId) return;
    await ops.createAdmission(facilityId, selectedWardId, bed.id);
    mutateBeds();
    mutateAdmissions();
  }

  async function discharge(admission: Admission) {
    await ops.dischargeAdmission(admission.id);
    mutateBeds();
    mutateAdmissions();
  }

  return (
    <div className="flex flex-col gap-8">
      {wardsError && <ErrorBanner message="Couldn't load wards." />}

      <div>
        {wardsLoading ? (
          <div className="flex gap-2">
            <Skeleton className="h-10 w-28 rounded-hig" />
            <Skeleton className="h-10 w-28 rounded-hig" />
          </div>
        ) : (
          <WardList wards={wards ?? []} selectedWardId={selectedWardId} onSelect={setSelectedWardId} />
        )}
      </div>

      {selectedWardId && (
        <section>
          <h2 className="text-title3 mb-3">Beds</h2>
          {bedsLoading ? (
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="aspect-square rounded-hig" />
              ))}
            </div>
          ) : (
            <BedGrid beds={beds ?? []} admissionByBedId={admissionByBedId} onAdmit={admit} onDischarge={discharge} />
          )}
        </section>
      )}

      <section>
        <h2 className="text-title3 mb-3">OT scheduling</h2>
        <OTScheduler
          slots={otSlots ?? []}
          wards={wards ?? []}
          onCreate={async (wardId, start, end) => {
            await ops.createOtSlot(facilityId, wardId, start, end);
            mutateOt();
          }}
        />
      </section>

      <section>
        <h2 className="text-title3 mb-3">Referrals</h2>
        <ReferralTracker
          referrals={referrals ?? []}
          facilityId={facilityId}
          destinationOptions={referralCandidates ?? []}
          onCreate={async (destFacilityId, reason, urgency: ReferralUrgency) => {
            await ops.createReferral({ sourceFacilityId: facilityId, destFacilityId, reason, urgency });
            mutateReferrals();
          }}
          onAdvanceStatus={async (referral) => {
            const next = referral.status === "OPEN" ? "ACKNOWLEDGED" : "CLOSED";
            await ops.updateReferralStatus(referral.id, next);
            mutateReferrals();
          }}
        />
      </section>
    </div>
  );
}
