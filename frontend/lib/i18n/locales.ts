// Single source of truth for every supported locale: code (BCP 47 primary-language subtag,
// matches backend `users.preferred_locale` exactly — see healthresq-interface-shapes.md's auth
// endpoints), the autonym shown in the language picker (never an English translation of the
// language's name — a lazy/illiterate-persona user reads their own script, not English), which
// script it renders in, and the Google Fonts family that covers that script. English/Latin is
// `null` — it rides the existing system-font stack in tokens.css, nothing extra to load.
//
// Scope note: India's Eighth Schedule has 22 languages; Kashmiri and Urdu are deliberately
// excluded (both conventionally Perso-Arabic/RTL in this context) so the whole app stays LTR —
// see the plan this was built from. Bodo, Konkani, and Sindhi are grouped under Devanagari, which
// is their standard script in the Indian context (as opposed to Sindhi's Perso-Arabic usage in
// Pakistan) — if that's ever wrong for a specific deployment, this is the one place to fix it.

export type Script =
  | "Latin"
  | "Devanagari"
  | "Bengali"
  | "Gujarati"
  | "Gurmukhi"
  | "Kannada"
  | "Malayalam"
  | "Oriya"
  | "Tamil"
  | "Telugu"
  | "OlChiki"
  | "MeeteiMayek";

export type Locale = {
  code: string;
  autonym: string;
  script: Script;
  /** Google Fonts CSS2 family name for this script, or null for the Latin system-font stack. */
  googleFontFamily: string | null;
  /** Machine-translated by default — flips to true only once a human/native-speaker review has
   * actually happened. Surfaced in the locale-README, not in the product UI itself. */
  reviewed: boolean;
};

export const LOCALES: Locale[] = [
  { code: "en", autonym: "English", script: "Latin", googleFontFamily: null, reviewed: true },
  { code: "hi", autonym: "हिन्दी", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "bn", autonym: "বাংলা", script: "Bengali", googleFontFamily: "Noto Sans Bengali", reviewed: false },
  { code: "as", autonym: "অসমীয়া", script: "Bengali", googleFontFamily: "Noto Sans Bengali", reviewed: false },
  { code: "brx", autonym: "बड़ो", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "doi", autonym: "डोगरी", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "gu", autonym: "ગુજરાતી", script: "Gujarati", googleFontFamily: "Noto Sans Gujarati", reviewed: false },
  { code: "kn", autonym: "ಕನ್ನಡ", script: "Kannada", googleFontFamily: "Noto Sans Kannada", reviewed: false },
  { code: "kok", autonym: "कोंकणी", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "mai", autonym: "मैथिली", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "ml", autonym: "മലയാളം", script: "Malayalam", googleFontFamily: "Noto Sans Malayalam", reviewed: false },
  { code: "mni", autonym: "ꯃꯤꯇꯩꯂꯣꯟ", script: "MeeteiMayek", googleFontFamily: "Noto Sans Meetei Mayek", reviewed: false },
  { code: "mr", autonym: "मराठी", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "ne", autonym: "नेपाली", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "or", autonym: "ଓଡ଼ିଆ", script: "Oriya", googleFontFamily: "Noto Sans Oriya", reviewed: false },
  { code: "pa", autonym: "ਪੰਜਾਬੀ", script: "Gurmukhi", googleFontFamily: "Noto Sans Gurmukhi", reviewed: false },
  { code: "sa", autonym: "संस्कृतम्", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "sat", autonym: "ᱥᱟᱱᱛᱟᱲᱤ", script: "OlChiki", googleFontFamily: "Noto Sans Ol Chiki", reviewed: false },
  { code: "sd", autonym: "सिन्धी", script: "Devanagari", googleFontFamily: "Noto Sans Devanagari", reviewed: false },
  { code: "ta", autonym: "தமிழ்", script: "Tamil", googleFontFamily: "Noto Sans Tamil", reviewed: false },
  { code: "te", autonym: "తెలుగు", script: "Telugu", googleFontFamily: "Noto Sans Telugu", reviewed: false },
];

export const LOCALE_CODES = LOCALES.map((l) => l.code);
export const DEFAULT_LOCALE = "en";

const LOCALE_MAP: Record<string, Locale> = Object.fromEntries(LOCALES.map((l) => [l.code, l]));
// "en" is always the first entry above — a non-null assertion here is safe and avoids threading
// `| undefined` through every caller of getLocale() for a value that can never actually be absent.
const FALLBACK_LOCALE: Locale = LOCALES[0]!;

export function getLocale(code: string | null | undefined): Locale {
  return (code && LOCALE_MAP[code]) || FALLBACK_LOCALE;
}

export function isSupportedLocale(code: string): boolean {
  return code in LOCALE_MAP;
}
