"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type ThemeChoice = "light" | "dark";
const STORAGE_KEY = "healthresq.theme";

const ThemeContext = createContext<{ theme: ThemeChoice; setTheme: (t: ThemeChoice) => void } | null>(null);

/** Light by default, always — never follows OS `prefers-color-scheme`. A user only ever sees dark
 * mode after explicitly choosing it (persisted); the inline script in app/layout.tsx stamps the
 * same default before hydration so there's no flash of the wrong theme on repeat visits. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>("light");

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    setThemeState(stored === "dark" ? "dark" : "light");
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const setTheme = (t: ThemeChoice) => {
    window.localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  };

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
