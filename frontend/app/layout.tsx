import type { Metadata } from "next";
import Script from "next/script";
import type { ReactNode } from "react";
import { Nav } from "@/components/Nav";
import { PageTransition } from "@/components/PageTransition";
import { AuthProvider } from "@/lib/auth/AuthContext";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { PerfProvider } from "@/lib/theme/PerfProvider";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { ToastProvider } from "@/lib/toast/ToastProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthResQ",
  description: "Federated agentic health-resource and supply-chain resilience platform",
};

// Server-rendered HTML already carries the light default below, so this only ever needs to flip
// the attribute for a returning user who chose dark — never for the (common) light case. Runs
// before hydration so that flip never flashes light-then-dark either.
const THEME_INIT_SCRIPT = `
  try {
    if (localStorage.getItem('healthresq.theme') === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch (e) {}
`;

// Same technique, for locale: server-rendered HTML already carries the English/Latin default
// below, so this only ever needs to act for a returning non-English user — stamping `lang` and
// loading that script's font `<link>` before first paint so there's no English-then-translated or
// tofu-boxes-then-glyphs flash. Duplicates locales.ts's code -> Google-font-family mapping (same
// tradeoff THEME_INIT_SCRIPT already accepts for the theme default) because this runs before any
// module import is possible — keep the two in sync if a locale's script/font ever changes.
const LOCALE_INIT_SCRIPT = `
  try {
    var locale = localStorage.getItem('healthresq.locale');
    var FONT = {
      hi:"Noto Sans Devanagari", bn:"Noto Sans Bengali", as:"Noto Sans Bengali",
      brx:"Noto Sans Devanagari", doi:"Noto Sans Devanagari", gu:"Noto Sans Gujarati",
      kn:"Noto Sans Kannada", kok:"Noto Sans Devanagari", mai:"Noto Sans Devanagari",
      ml:"Noto Sans Malayalam", mni:"Noto Sans Meetei Mayek", mr:"Noto Sans Devanagari",
      ne:"Noto Sans Devanagari", or:"Noto Sans Oriya", pa:"Noto Sans Gurmukhi",
      sa:"Noto Sans Devanagari", sat:"Noto Sans Ol Chiki", sd:"Noto Sans Devanagari",
      ta:"Noto Sans Tamil", te:"Noto Sans Telugu"
    };
    if (locale && locale !== 'en') {
      document.documentElement.setAttribute('lang', locale);
      var family = FONT[locale];
      if (family) {
        document.documentElement.style.setProperty('--font-sans-active', '"' + family + '", var(--font-sans)');
        var link = document.createElement('link');
        link.id = 'healthresq-script-font';
        link.rel = 'stylesheet';
        link.href = 'https://fonts.googleapis.com/css2?family=' + family.replace(/ /g, '+') + ':wght@400;500;600;700&display=swap';
        document.head.appendChild(link);
      }
    }
  } catch (e) {}
`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <Script id="locale-init" strategy="beforeInteractive">
          {LOCALE_INIT_SCRIPT}
        </Script>
      </head>
      <body className="bg-bg-secondary min-h-screen">
        <ThemeProvider>
          <PerfProvider>
            <ToastProvider>
              <LocaleProvider>
                <AuthProvider>
                  <Nav />
                  <main className="max-w-5xl mx-auto px-4 py-6">
                    <PageTransition>{children}</PageTransition>
                  </main>
                </AuthProvider>
              </LocaleProvider>
            </ToastProvider>
          </PerfProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
