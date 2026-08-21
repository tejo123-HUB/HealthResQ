"use client";

import { AuthGuard } from "@/components/AuthGuard";
import { FacilityHome } from "@/components/FacilityHome";
import { useAuth } from "@/lib/auth/AuthContext";

function Workspace() {
  const { facility } = useAuth();
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-title1">{facility!.name}</h1>
      <FacilityHome />
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
