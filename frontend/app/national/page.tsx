"use client";

import { AuthGuard } from "@/components/AuthGuard";
import { DashboardScreen } from "@/components/DashboardScreen";
import { useAuth } from "@/lib/auth/AuthContext";

function Workspace() {
  const { scope } = useAuth();
  return <DashboardScreen level="NATIONAL" scopeId={scope!.id} />;
}

export default function Page() {
  return (
    <AuthGuard>
      <Workspace />
    </AuthGuard>
  );
}
