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

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: DEFAULT_LANG,
    supportedLngs: AVAILABLE_LANGS,
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
