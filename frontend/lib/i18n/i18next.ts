import i18next from "i18next";
import HttpBackend from "i18next-http-backend";
import { initReactI18next } from "react-i18next";
import { DEFAULT_LOCALE, LOCALE_CODES } from "@/lib/i18n/locales";

// English namespace files are imported statically (bundled, synchronous) rather than fetched —
// every other locale is fetched lazily via HttpBackend below. This is what makes English safe as
// the always-available fallback: SSR and the pre-hydration client render both need real English
// text available with zero network round-trip, or the server HTML (raw `en` text) and the client's
// first render (raw translation *keys*, before an async fetch resolves) would disagree and React
// would throw a hydration-mismatch error. Every other locale only ever gets applied after mount
// (LocaleProvider's effect / AuthContext's login flow), by which point a mismatch can't occur —
// so only English needs this treatment.
import enCommon from "@/public/locales/en/common.json";
import enNav from "@/public/locales/en/nav.json";
import enLogin from "@/public/locales/en/login.json";
import enDashboard from "@/public/locales/en/dashboard.json";
import enHms from "@/public/locales/en/hms.json";
import enRecommendations from "@/public/locales/en/recommendations.json";
import enAgent from "@/public/locales/en/agent.json";
import enMailbox from "@/public/locales/en/mailbox.json";
import enErrors from "@/public/locales/en/errors.json";

export const NAMESPACES = [
  "common",
  "nav",
  "login",
  "dashboard",
  "hms",
  "recommendations",
  "agent",
  "mailbox",
  "errors",
] as const;

const EN_RESOURCES = {
  common: enCommon,
  nav: enNav,
  login: enLogin,
  dashboard: enDashboard,
  hms: enHms,
  recommendations: enRecommendations,
  agent: enAgent,
  mailbox: enMailbox,
  errors: enErrors,
};

// Every other locale fetches `/locales/{{lng}}/{{ns}}.json` (i18next-http-backend, plain `fetch`)
// at runtime instead of being statically imported — a locale most users never pick shouldn't be in
// the initial JS bundle. Initialized once per app load; `changeLanguage` (called from
// LocaleProvider/AuthContext) lazily fetches whatever the active locale doesn't have cached yet.
if (!i18next.isInitialized) {
  i18next
    .use(HttpBackend)
    .use(initReactI18next)
    .init({
      lng: DEFAULT_LOCALE,
      fallbackLng: DEFAULT_LOCALE,
      supportedLngs: LOCALE_CODES,
      ns: NAMESPACES,
      defaultNS: "common",
      resources: { [DEFAULT_LOCALE]: EN_RESOURCES },
      partialBundledLanguages: true,
      backend: { loadPath: "/locales/{{lng}}/{{ns}}.json" },
      interpolation: { escapeValue: false }, // React already escapes
      react: { useSuspense: false },
    });
}

export default i18next;
