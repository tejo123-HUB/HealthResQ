"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/lib/auth/AuthContext";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { scope, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !scope) router.replace("/login");
  }, [loading, scope, router]);

  if (loading || !scope) {
    return <LoadingScreen />;
  }

  return <>{children}</>;
}
