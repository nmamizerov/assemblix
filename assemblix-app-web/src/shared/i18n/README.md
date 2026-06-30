# Internationalization (i18n)

This project uses `react-i18next`. The app currently ships **English only**, but all
user-facing text goes through `t()` so additional locales can be added later.

## Structure

```
src/shared/i18n/
├── index.ts              # i18next configuration
├── types.ts              # TypeScript types
├── locales/
│   └── en.json           # English translations
└── README.md             # This documentation
```

## Using it in components

```tsx
import { useTranslation } from 'react-i18next';

function MyComponent() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('common.title')}</h1>
      <p>{t('common.description')}</p>
    </div>
  );
}
```

## Translations with parameters

```tsx
// In JSON:
{
  "greeting": "Hello, {{name}}!"
}

// In a component:
<p>{t('greeting', { name: 'Ada' })}</p>
```

## Build

```bash
yarn build
```

The bundled locales are controlled by `VITE_LANGS` (default `en`).

## Adding new translation keys

Add the key to `locales/en.json`:

```json
{
  "myFeature": {
    "title": "Title"
  }
}
```

Then use it in a component:

```tsx
const { t } = useTranslation();
<h1>{t('myFeature.title')}</h1>
```
