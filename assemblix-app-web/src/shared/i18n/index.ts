import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en.json";

// Available languages come from build-time env vars.
export const AVAILABLE_LANGS =
  typeof __AVAILABLE_LANGS__ !== "undefined" ? __AVAILABLE_LANGS__ : ["en"];

export const DEFAULT_LANG =
  typeof __DEFAULT_LANG__ !== "undefined" ? __DEFAULT_LANG__ : "en";

// Build the resources object only with available languages.
const resources: Record<string, { translation: typeof en }> = {};

AVAILABLE_LANGS.forEach((lang) => {
  if (lang === "en") {
    resources.en = { translation: en };
  }
});

// Only these languages actually ship translations (currently English only).
// `AVAILABLE_LANGS` / `DEFAULT_LANG` come from build-time env and may name a
// language we don't bundle yet — resolving to it leaves the UI without strings.
const BUNDLED_LANGS = Object.keys(resources);
const FALLBACK_LANG = BUNDLED_LANGS.includes(DEFAULT_LANG) ? DEFAULT_LANG : "en";

// Returning users may have cached a now-unbundled language (e.g. "ru") from an
// earlier build, which left their UI without English strings. Force everyone
// back onto a bundled language by dropping that stale cache before detection
// runs. Self-healing on every load; also corrects the value read for the API
// `Accept-Language` header (see shared/api/baseApi.ts).
try {
  const cached = localStorage.getItem("i18nextLng");
  if (cached && !BUNDLED_LANGS.includes(cached)) {
    localStorage.setItem("i18nextLng", FALLBACK_LANG);
  }
} catch {
  // localStorage unavailable (e.g. privacy mode) — detection falls back safely.
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: FALLBACK_LANG,
    // Restrict to bundled languages so neither localStorage nor navigator can
    // select a language we don't ship translations for.
    supportedLngs: BUNDLED_LANGS,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
  });

export default i18n;
