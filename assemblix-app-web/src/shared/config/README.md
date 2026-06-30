# Конфигурация приложения

Централизованное хранилище всех настроек и environment переменных приложения.

## Использование

```typescript
import { config, oauthConfig, apiConfig } from "@/shared/config";

// Использование OAuth конфигурации
console.log(oauthConfig.google.clientId);

// Использование API конфигурации
console.log(apiConfig.baseUrl);

// Полная конфигурация
console.log(config.app.name); // "Assemblix"
console.log(config.oauth.google.enabled); // true/false
```

## Структура

### OAuth конфигурация (`oauthConfig`)

Настройки для OAuth провайдеров:
- `google` - Google OAuth
- `github` - GitHub OAuth (для будущей реализации)
- `yandex` - Yandex OAuth (для будущей реализации)

Каждый провайдер имеет:
- `clientId` - Client ID из environment переменной
- `enabled` - автоматически определяется наличием Client ID

### API конфигурация (`apiConfig`)

Настройки API:
- `baseUrl` - базовый URL для API запросов (по умолчанию `/api`)
- `timeout` - таймаут для запросов в миллисекундах

### Приложение (`appConfig`)

Общие настройки:
- `name` - название приложения
- `version` - версия приложения
- `env` - окружение (development/production)
- `isDevelopment` - флаг режима разработки
- `isProduction` - флаг продакшн режима

### Локализация (`i18nConfig`)

Настройки i18n:
- `defaultLanguage` - язык по умолчанию (из `VITE_DEFAULT_LANGUAGE` или `"en"`)
- `supportedLanguages` - поддерживаемые языки (из `VITE_SUPPORTED_LANGUAGES` или `["en"]`)
- `storageKey` - ключ для localStorage

**Примечание:** `VITE_SUPPORTED_LANGUAGES` должна быть строкой с языками через запятую, например: `"ru,en,de,fr"`

### Тема (`themeConfig`)

Настройки темы:
- `storageKey` - ключ для localStorage
- `defaultTheme` - тема по умолчанию

## Environment переменные

Создайте файл `.env` в корне проекта:

```bash
# OAuth
VITE_GOOGLE_CLIENT_ID=your_google_client_id
VITE_GITHUB_CLIENT_ID=your_github_client_id
VITE_YANDEX_CLIENT_ID=your_yandex_client_id

# i18n
VITE_SUPPORTED_LANGUAGES=ru,en,de,fr
VITE_DEFAULT_LANGUAGE=ru

# API
VITE_API_BASE_URL=/api

# App
VITE_APP_VERSION=1.0.0
```

## Добавление новых настроек

1. Добавьте environment переменную в `.env`
2. Добавьте конфигурацию в соответствующий раздел `app.config.ts`
3. Экспортируйте через `index.ts` если необходимо
4. Обновите документацию

### Пример добавления нового провайдера OAuth:

```typescript
export const oauthConfig = {
  google: { /* ... */ },
  github: { /* ... */ },
  yandex: { /* ... */ },
  // Новый провайдер:
  facebook: {
    clientId: import.meta.env.VITE_FACEBOOK_CLIENT_ID || "",
    enabled: Boolean(import.meta.env.VITE_FACEBOOK_CLIENT_ID),
  },
} as const;
```

## TypeScript

Все конфигурации типизированы и помечены как `as const` для максимальной безопасности типов.

```typescript
// Автоматическая проверка типов
const clientId: string = oauthConfig.google.clientId; // ✅ OK
const enabled: boolean = oauthConfig.google.enabled; // ✅ OK
```
