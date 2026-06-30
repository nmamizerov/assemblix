import type { Plugin } from "vite";
import { htmlMeta, type HtmlMetaLang } from "./src/shared/i18n/html-meta";

export function htmlI18nPlugin(lang: string): Plugin {
  const meta = htmlMeta[(lang as HtmlMetaLang) in htmlMeta ? (lang as HtmlMetaLang) : "en"];

  return {
    name: "html-i18n",
    transformIndexHtml(html) {
      return html
        .replace(/%HTML_LANG%/g, meta.lang)
        .replace(/%HTML_LANGUAGE%/g, meta.language)
        .replace(/%HTML_LOCALE%/g, meta.locale)
        .replace(/%HTML_TITLE%/g, meta.title)
        .replace(/%HTML_DESCRIPTION%/g, meta.description)
        .replace(/%HTML_KEYWORDS%/g, meta.keywords)
        .replace(/%HTML_STRUCTURED_APP_DESCRIPTION%/g, meta.structuredAppDescription)
        .replace(/%HTML_STRUCTURED_ORG_DESCRIPTION%/g, meta.structuredOrgDescription);
    },
  };
}
