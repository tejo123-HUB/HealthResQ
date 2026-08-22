"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "@/components/hig/Icon";
import { LanguageSheet } from "@/components/LanguageSheet";
import { useAuth } from "@/lib/auth/AuthContext";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { useAdaptiveEffects } from "@/lib/theme/PerfProvider";
import { useTheme } from "@/lib/theme/ThemeProvider";

/** One role, one workspace: every screen a signed-in user needs lives at a single destination
 * (their role's workspace, organized internally with tabs), so there is nothing left to put in a
 * navigation bar except identity and the account-level actions. Minimal by construction, not
 * by hiding things — there's simply nowhere else to go. */
export function Nav() {
  const { t } = useTranslation(["nav", "common"]);
  const { scope, facility, logout, updateLocale } = useAuth();
  const { locale } = useLocale();
  const { theme, setTheme } = useTheme();
  const { glassEnabled } = useAdaptiveEffects();
  const [scrolled, setScrolled] = useState(false);
  const [languageOpen, setLanguageOpen] = useState(false);

  // A flat border reads fine at the very top of a page; once content is scrolling underneath,
  // a soft shadow gives the bar real separation instead of content looking like it's clipping
  // through it — the same depth cue iOS/macOS bars pick up once there's something to float above.
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!scope) return null;

  const themeIcon = theme === "dark" ? "moon" : "sun";

  return (
    <nav
      className={`sticky top-0 z-10 bg-fill-thick border-b transition-shadow duration-300 ${
        glassEnabled ? "backdrop-blur-xl" : ""
      } ${scrolled ? "border-separator shadow-[0_1px_12px_rgba(0,0,0,0.06)]" : "border-transparent"}`}
    >
      <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-white flex items-center justify-center overflow-hidden shrink-0 ring-1 ring-separator shadow-sm">
            <Image src="/logo.png" alt="HealthResQ" width={28} height={28} />
          </div>
          <div className="min-w-0">
            <p
              className="text-subhead font-semibold leading-none truncate"
              title={facility ? facility.name : t(`nav:scopeLevel.${scope.level}`)}
            >
              {facility ? facility.name : t(`nav:scopeLevel.${scope.level}`)}
            </p>
            <p className="text-caption2 text-label-tertiary">HealthResQ</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setLanguageOpen(true)}
            aria-label={t("common:language")}
            className="w-9 h-9 flex items-center justify-center rounded-hig text-label-secondary hover:bg-fill-thin active:bg-fill-regular active:scale-90 transition-hig"
          >
            <Icon name="globe" className="w-4.5 h-4.5" />
          </button>
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={t("nav:toggleTheme")}
            className="w-9 h-9 flex items-center justify-center rounded-hig text-label-secondary hover:bg-fill-thin active:bg-fill-regular active:scale-90 transition-hig overflow-hidden"
          >
            <span key={theme} className="animate-scale-in inline-flex">
              <Icon name={themeIcon} className="w-4.5 h-4.5" />
            </span>
          </button>
          <button
            onClick={logout}
            aria-label={t("nav:signOut")}
            className="w-9 h-9 flex items-center justify-center rounded-hig text-tint-red hover:bg-tint-red-wash active:bg-fill-regular active:scale-90 transition-hig"
          >
            <Icon name="signOut" className="w-4.5 h-4.5" />
          </button>
        </div>
      </div>
      <LanguageSheet
        open={languageOpen}
        current={locale}
        onSelect={(code) => {
          updateLocale(code);
          setLanguageOpen(false);
        }}
        onDismiss={() => setLanguageOpen(false)}
      />
    </nav>
  );
}
