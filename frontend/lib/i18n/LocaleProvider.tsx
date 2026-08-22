"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { applyScriptFont } from "@/lib/i18n/fonts";
import i18n from "@/lib/i18n/i18next";
import { DEFAULT_LOCALE, getLocale, isSupportedLocale } from "@/lib/i18n/locales";

const STORAGE_KEY = "healthresq.locale";

type LocaleState = {
  locale: string;
  /** Switches the active language immediately (i18next + font + `<html lang>`) and caches the
   * choice in localStorage so it survives a reload before any account sync (AuthContext) can run.
   * Does NOT talk to the backend — callers that want it bound to the signed-in account persist it
   * separately (see AuthContext.setPreferredLocale), the same optimistic-then-sync split the plan
   * calls for. */
  setLocale: (code: string) => void;
};

const LocaleContext = createContext<LocaleState | null>(null);

function readStoredLocale(): string {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && isSupportedLocale(stored) ? stored : DEFAULT_LOCALE;
}

/** Mirrors ThemeProvider's shape exactly: English/`en` is the always-safe default the server
 * already rendered (see the pre-hydration script in app/layout.tsx), and this effect only ever
 * needs to *change* something for a returning non-English user — never for the common case. */
export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = readStoredLocale();
    if (stored !== DEFAULT_LOCALE) {
      i18n.changeLanguage(stored);
      applyScriptFont(getLocale(stored));
    }
    setLocaleState(stored);
  }, []);

  const setLocale = (code: string) => {
    if (!isSupportedLocale(code)) return;
    window.localStorage.setItem(STORAGE_KEY, code);
    i18n.changeLanguage(code);
    document.documentElement.lang = code;
    applyScriptFont(getLocale(code));
    setLocaleState(code);
  };

  return (
    <I18nextProvider i18n={i18n}>
      <LocaleContext.Provider value={{ locale, setLocale }}>{children}</LocaleContext.Provider>
    </I18nextProvider>
  );
}

export function useLocale(): LocaleState {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
