import { useTranslation } from "react-i18next";

const LOCALE_MAP: Record<string, string> = {
  ru: "ru-RU",
  en: "en-US",
  es: "es-ES",
};

function toLocale(lang: string): string {
  return LOCALE_MAP[lang] ?? "en-US";
}

function toDate(date: Date | string | number): Date {
  return date instanceof Date ? date : new Date(date);
}

/** "3 янв, 14:05" / "Jan 3, 02:05 PM" */
export function formatShortDateTime(date: Date | string | number, locale: string): string {
  return toDate(date).toLocaleString(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "3 янв 2025, 14:05" / "Jan 3, 2025, 02:05 PM" */
export function formatDateTime(date: Date | string | number, locale: string): string {
  return toDate(date).toLocaleString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "3 января 2025" / "January 3, 2025" */
export function formatLongDate(date: Date | string | number, locale: string): string {
  return toDate(date).toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** "3 января 2025, 14:05" / "January 3, 2025, 02:05 PM" */
export function formatLongDateTime(date: Date | string | number, locale: string): string {
  return toDate(date).toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "03.01.2025" / "01/03/2025" */
export function formatShortDate(date: Date | string | number, locale: string): string {
  return toDate(date).toLocaleDateString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Форматирование числа с разделителями тысяч */
export function formatNumber(value: number, locale: string): string {
  return value.toLocaleString(locale);
}

/** Хук, возвращающий функции форматирования, привязанные к текущему языку интерфейса */
export function useFormatDate() {
  const { i18n } = useTranslation();
  const locale = toLocale(i18n.language);

  return {
    formatShortDateTime: (date: Date | string | number) => formatShortDateTime(date, locale),
    formatDateTime: (date: Date | string | number) => formatDateTime(date, locale),
    formatLongDate: (date: Date | string | number) => formatLongDate(date, locale),
    formatLongDateTime: (date: Date | string | number) => formatLongDateTime(date, locale),
    formatShortDate: (date: Date | string | number) => formatShortDate(date, locale),
    formatNumber: (value: number) => formatNumber(value, locale),
  };
}
