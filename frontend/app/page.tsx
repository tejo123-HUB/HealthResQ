"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/lib/auth/AuthContext";
import { homePathForScope } from "@/lib/auth/routing";

export default function RootPage() {
  const { t } = useTranslation("common");
  const { scope, facility, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!scope) {
      router.replace("/login");
      return;
    }
    router.replace(homePathForScope(scope.level, facility?.type));
  }, [loading, scope, facility, router]);

  return <LoadingScreen message={t("signingYouIn")} />;
}
