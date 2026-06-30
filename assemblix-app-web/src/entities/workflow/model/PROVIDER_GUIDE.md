# Руководство по добавлению нового провайдера

Система конфигурации провайдеров позволяет легко добавлять новые AI-провайдеры без изменения кода форм.

## Как добавить новый провайдер

### Шаг 1: Добавить enum в Provider

Откройте файл `types.ts` и добавьте новый провайдер в enum:

```typescript
export enum Provider {
  OPENAI = "openai",
  GEMINI = "gemini",
  ANTHROPIC = "anthropic", // Новый провайдер
}
```

### Шаг 2: Добавить тип credential

Откройте файл `src/entities/credential/model/types.ts` и добавьте новый тип credential:

```typescript
export enum CredentialType {
  OPENAI_TOKEN = "openai_token",
  GEMINI_TOKEN = "gemini_token",
  ANTHROPIC_TOKEN = "anthropic_token", // Новый тип
}
```

### Шаг 3: Создать конфигурацию провайдера

Откройте файл `providers.config.ts` и добавьте конфигурацию:

```typescript
const anthropicConfig: ProviderConfig = {
  provider: Provider.ANTHROPIC,
  label: "Anthropic (Claude)",
  credentialType: CredentialType.ANTHROPIC_TOKEN,
  fields: [
    {
      key: "temperature",
      label: "Температура",
      type: FieldType.NUMBER,
      defaultValue: 1.0,
      placeholder: "1.0",
      validation: {
        min: 0,
        max: 1,
        step: 0.1,
        required: false,
      },
      helpText: "Контролирует случайность ответов (0-1)",
    },
    {
      key: "max_tokens",
      label: "Максимум токенов",
      type: FieldType.NUMBER,
      defaultValue: 1024,
      placeholder: "1024",
      validation: {
        min: 1,
        max: 200000,
        step: 1,
        required: false,
      },
      helpText: "Максимальное количество токенов в ответе",
    },
    // ... другие поля специфичные для Anthropic
  ],
};
```

### Шаг 4: Добавить конфигурацию в маппинг

В том же файле добавьте новую конфигурацию в объект `PROVIDERS_CONFIG`:

```typescript
export const PROVIDERS_CONFIG: ProvidersConfigMap = {
  [Provider.OPENAI]: openAIConfig,
  [Provider.GEMINI]: geminiConfig,
  [Provider.ANTHROPIC]: anthropicConfig, // Добавить здесь
};
```

### Шаг 5: Обновить UI для выбора провайдера

Откройте файл `agent-node-form.tsx` и добавьте новый провайдер в список:

```tsx
<SelectContent>
  <SelectItem value="openai" className="text-xs">
    OpenAI
  </SelectItem>
  <SelectItem value="gemini" className="text-xs">
    Gemini
  </SelectItem>
  <SelectItem value="anthropic" className="text-xs">
    Anthropic
  </SelectItem>
</SelectContent>
```

## Готово! 🎉

Теперь новый провайдер появится в форме с автоматически отрисованными полями. Никаких других изменений в коде не требуется!

## Доступные типы полей

- `FieldType.INPUT` - текстовое поле
- `FieldType.NUMBER` - числовое поле с валидацией min/max/step
- `FieldType.SELECT` - выпадающий список с опциями
- `FieldType.TEXTAREA` - многострочное текстовое поле
- `FieldType.SWITCH` - переключатель (boolean)

## Опции валидации

```typescript
{
  required?: boolean;      // Обязательное поле
  min?: number;           // Минимальное значение (для number)
  max?: number;           // Максимальное значение (для number)
  step?: number;          // Шаг изменения (для number)
  pattern?: string;       // Регулярное выражение (для input)
  message?: string;       // Сообщение об ошибке
}
```

## Пример полной конфигурации поля

```typescript
{
  key: "temperature",              // Ключ поля в объекте данных
  label: "Температура",            // Отображаемое название
  type: FieldType.NUMBER,          // Тип поля
  defaultValue: 0.7,               // Значение по умолчанию
  placeholder: "0.7",              // Placeholder
  validation: {                    // Правила валидации
    min: 0,
    max: 2,
    step: 0.1,
    required: false,
  },
  helpText: "Контролирует случайность", // Подсказка
}
```

