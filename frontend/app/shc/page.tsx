"use client";

import { useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { FacilityHome } from "@/components/FacilityHome";
import { HmsWorkspace } from "@/components/hms/HmsWorkspace";
import { SegmentedControl } from "@/components/hig/SegmentedControl";
import { useAuth } from "@/lib/auth/AuthContext";

type Tab = "OVERVIEW" | "HOSPITAL";

/** SHC's one workspace — Overview (OPS-06) and Hospital (OPS-11-13) are tabs on the same page,
 * not separate nav destinations: an operator has exactly one place to be. */
function Workspace() {
  const { facility } = useAuth();
  const [tab, setTab] = useState<Tab>("OVERVIEW");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-title1">{facility!.name}</h1>
        <SegmentedControl
          value={tab}
          onChange={setTab}
          options={[
            { value: "OVERVIEW", label: "Overview" },
            { value: "HOSPITAL", label: "Hospital" },
          ]}
        />
      </div>
      {tab === "OVERVIEW" ? <FacilityHome /> : <HmsWorkspace facilityId={facility!.id} />}
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <Workspace />
    </AuthGuard>
  );
}
