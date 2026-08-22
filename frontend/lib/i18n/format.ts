// Locale-aware wrappers around the 4 unlocalized `toLocaleString()` call sites the i18n readiness
// audit found (InstructionList, InboxPanel, OTScheduler, Card's StatCard) — those previously left
// date/number formatting to whatever the browser's ambient locale happened to be, which could
// silently mismatch the app's own (user-chosen) locale. `Intl` already understands every BCP 47
// code in locales.ts natively; no extra formatting library needed.

export function formatDate(date: Date | string | number, locale: string): string {
  return new Intl.DateTimeFormat(locale).format(new Date(date));
}

export function formatTime(date: Date | string | number, locale: string): string {
  return new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit" }).format(new Date(date));
}

export function formatDateTime(date: Date | string | number, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(date));
}

export function formatNumber(n: number, locale: string): string {
  return new Intl.NumberFormat(locale).format(n);
}
