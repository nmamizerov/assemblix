const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

const STORAGE_KEY = "assemblix_utm_params";

export type UtmParams = Partial<Record<(typeof UTM_KEYS)[number], string>>;

export function captureUtmParams(): UtmParams {
  const searchParams = new URLSearchParams(window.location.search);
  const utm: UtmParams = {};

  for (const key of UTM_KEYS) {
    const value = searchParams.get(key);
    if (value) {
      utm[key] = value;
    }
  }

  return utm;
}

export function saveUtmToStorage(utm: UtmParams): void {
  if (Object.keys(utm).length === 0) return;

  const existing = getUtmFromStorage();
  if (existing && Object.keys(existing).length > 0) return;

  localStorage.setItem(STORAGE_KEY, JSON.stringify(utm));
}

export function getUtmFromStorage(): UtmParams | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearUtmFromStorage(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/**
 * Возвращает UTM-параметры в camelCase для отправки на бэкенд.
 * snake_case -> camelCase конвертация произойдёт автоматически в API слое,
 * но тут мы маппим ключи явно для типобезопасности.
 */
export function getUtmForRegistration(): {
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmContent?: string;
  utmTerm?: string;
} | null {
  const utm = getUtmFromStorage();
  if (!utm || Object.keys(utm).length === 0) return null;

  return {
    ...(utm.utm_source && { utmSource: utm.utm_source }),
    ...(utm.utm_medium && { utmMedium: utm.utm_medium }),
    ...(utm.utm_campaign && { utmCampaign: utm.utm_campaign }),
    ...(utm.utm_content && { utmContent: utm.utm_content }),
    ...(utm.utm_term && { utmTerm: utm.utm_term }),
  };
}
