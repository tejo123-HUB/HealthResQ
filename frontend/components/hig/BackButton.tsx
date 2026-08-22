"use client";

import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/hig/Icon";

/** Nav carries no links (each role has exactly one workspace), so a page reached via an in-workspace
 * action — not the workspace itself — needs its own way back. Browser/router back, not a fixed
 * href, so it always returns to wherever the user actually came from. */
export function BackButton() {
  const router = useRouter();
  const { t } = useTranslation("common");
  return (
    <button
      onClick={() => router.back()}
      className="group flex items-center gap-1 text-body text-tint-blue mb-2 -ml-2 px-2 py-1 rounded-hig hover:bg-fill-thin active:bg-fill-regular transition-hig"
    >
      <Icon name="chevronLeft" className="w-5 h-5 transition-transform group-hover:-translate-x-0.5" />
      {t("back")}
    </button>
  );
}
