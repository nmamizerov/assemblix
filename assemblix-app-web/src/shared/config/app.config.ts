/**
 * Централизованная конфигурация приложения
 * Все environment переменные и настройки приложения хранятся здесь
 */

/**
 * OAuth конфигурация
 */
export const oauthConfig = {
  google: {
    clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID || "",
    enabled: Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID),
  },
  github: {
    clientId: import.meta.env.VITE_GITHUB_CLIENT_ID || "",
    enabled: Boolean(import.meta.env.VITE_GITHUB_CLIENT_ID),
  },
  yandex: {
    clientId: import.meta.env.VITE_YANDEX_CLIENT_ID || "",
    enabled: Boolean(import.meta.env.VITE_YANDEX_CLIENT_ID),
  },
} as const;

/**
 * API конфигурация
 */
export const apiConfig = {
  baseUrl: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 30000,
} as const;

/**
 * Биллинг (коммерческая сборка). При false вся платёжная часть UI скрыта.
 */
export const billingConfig = {
  enabled: import.meta.env.VITE_BILLING_ENABLED === "true",
} as const;

export const isBillingEnabled = billingConfig.enabled;

/**
 * Общие настройки приложения
 */
export const appConfig = {
  name: "Assemblix",
  url: import.meta.env.VITE_APP_URL || window.location.origin,
  version: import.meta.env.VITE_APP_VERSION || "1.0.0",
  env: import.meta.env.MODE || "development",
  isDevelopment: import.meta.env.DEV,
  isProduction: import.meta.env.PROD,
} as const;

/**
 * Локализация
 */
export const i18nConfig = {
  defaultLanguage: import.meta.env.VITE_DEFAULT_LANGUAGE || "en",
  supportedLanguages: import.meta.env.VITE_SUPPORTED_LANGUAGES
    ? import.meta.env.VITE_SUPPORTED_LANGUAGES.split(",")
    : ["en"],
  storageKey: "assemblix-language",
} as const;

/**
 * Тема
 */
export const themeConfig = {
  storageKey: "assemblix-theme",
  defaultTheme: "light" as const,
} as const;

/**
 * Экспорт всей конфигурации
 */
export const config = {
  app: appConfig,
  api: apiConfig,
  oauth: oauthConfig,
  i18n: i18nConfig,
  theme: themeConfig,
  billing: billingConfig,
} as const;

export default config;
