# Assemblix Web

React 19 + Vite + TypeScript frontend for **Assemblix** — the visual workflow canvas. Built
with [React Flow](https://reactflow.dev) (`@xyflow/react`), Redux Toolkit + RTK Query,
Tailwind CSS 4, and shadcn/ui, following [Feature-Sliced Design](https://feature-sliced.design).

> New here? Start with the **[root README](../README.md)** for the one-command quickstart
> that runs the whole stack (web + api + db).

## Run it

Configuration comes from the **single `.env` at the repo root** (`../.env`). For native host
development the backend is expected at `http://localhost:8000` (Vite proxies `/api/` there):

```bash
yarn install
yarn dev          # Vite dev server (HMR) → http://localhost:5173
yarn dev:en       # …with the English locale
yarn build        # type-check + production build
yarn lint         # ESLint
```

## Architecture

Strict FSD layering with unidirectional imports: `app → pages → features → entities →
shared`. The canvas lives in `src/entities/workflow/lib/workflow-editor/` (nodes,
node-forms, debug panel). API calls go through `baseApi.injectEndpoints()`; all
user-facing text uses i18n. Backend `snake_case` ↔ frontend `camelCase` is converted
automatically. Full conventions and slice structure are in **[CLAUDE.md](CLAUDE.md)**.

## License

Source-available: **MIT + Commons Clause** ([../LICENSE.md](../LICENSE.md)). See
[../NOTICE](../NOTICE) for third-party attributions.
