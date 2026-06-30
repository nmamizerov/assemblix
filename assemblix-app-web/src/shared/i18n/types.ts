import en from "./locales/en.json";

export type TranslationResource = typeof en;

declare global {
  const __AVAILABLE_LANGS__: string[];
  const __DEFAULT_LANG__: string;
}
