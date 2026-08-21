"use client";

import Image from "next/image";
import { Icon } from "@/components/hig/Icon";
import { useAuth } from "@/lib/auth/AuthContext";
import { useTheme } from "@/lib/theme/ThemeProvider";

/** One role, one workspace: every screen a signed-in user needs lives at a single destination
 * (their role's workspace, organized internally with tabs), so there is nothing left to put in a
 * navigation bar except identity and the two account-level actions. Minimal by construction, not
 * by hiding things — there's simply nowhere else to go. */
export function Nav() {
  const { scope, facility, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  if (!scope) return null;

  const themeIcon = theme === "dark" ? "moon" : "sun";

  return (
    <nav className="sticky top-0 z-10 backdrop-blur-xl bg-fill-thick border-b border-separator">
      <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center overflow-hidden shrink-0 ring-1 ring-separator shadow-sm">
            <Image src="/logo.png" alt="HealthResQ" width={32} height={32} />
          </div>
          <div>
            <p className="text-headline leading-none">{facility ? facility.name : scope.level}</p>
            <p className="text-caption2 text-label-tertiary">HealthResQ</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
            className="w-11 h-11 flex items-center justify-center rounded-hig text-label-secondary hover:bg-fill-thin active:bg-fill-regular active:scale-90 transition-hig overflow-hidden"
          >
            <span key={theme} className="animate-scale-in inline-flex">
              <Icon name={themeIcon} />
            </span>
          </button>
          <button
            onClick={logout}
            aria-label="Sign out"
            className="w-11 h-11 flex items-center justify-center rounded-hig text-tint-red hover:bg-tint-red-wash active:bg-fill-regular active:scale-90 transition-hig"
          >
            <Icon name="signOut" />
          </button>
        </div>
      </div>
    </nav>
  );
}
