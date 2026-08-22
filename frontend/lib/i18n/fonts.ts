import type { Locale } from "@/lib/i18n/locales";

const LINK_ID = "healthresq-script-font";

/** Injects (or swaps) a single Google Fonts `<link>` for the active locale's script, and clears it
 * entirely for Latin locales — so English/Latin stays byte-identical to today (nothing extra ever
 * loads) and only one non-Latin font family is ever in flight at a time. Runtime-injected rather
 * than a `next/font` static import because locale is client-side state here, not a route segment
 * (see the plan's step 1) — there's no per-locale page for `next/font` to attach to. */
export function applyScriptFont(locale: Locale) {
  if (typeof document === "undefined") return;
  const existing = document.getElementById(LINK_ID);

  if (!locale.googleFontFamily) {
    existing?.remove();
    document.documentElement.removeAttribute("data-script");
    document.documentElement.style.removeProperty("--font-sans-active");
    return;
  }

  const family = locale.googleFontFamily.replace(/ /g, "+");
  const href = `https://fonts.googleapis.com/css2?family=${family}:wght@400;500;600;700&display=swap`;

  // Set the active-font variable immediately (even before the stylesheet finishes loading) so the
  // browser's own font-fallback machinery — not a manual "wait for load" step — handles the swap;
  // `display=swap` in the URL means the fallback stack renders first, then reflows once the
  // webfont is ready, exactly like a normal webfont load.
  document.documentElement.style.setProperty(
    "--font-sans-active",
    `"${locale.googleFontFamily}", var(--font-sans)`
  );
  document.documentElement.setAttribute("data-script", locale.script);

  if (existing instanceof HTMLLinkElement && existing.href === href) return;

  const link = document.createElement("link");
  link.id = LINK_ID;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
  existing?.remove();
}
