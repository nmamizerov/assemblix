# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Assemblix** — a visual AI agent/workflow builder platform. Users create workflows on a React Flow canvas by connecting nodes (START, AGENT, CONDITION, SET_VARIABLE, END, HTTP_REQUEST, STICKER), then execute and monitor them. Supports multiple LLM providers (OpenAI, Gemini, DeepSeek).

## Commands

```bash
npm run dev          # Dev server (English locale)
npm run build        # TypeScript check + production build
npm run lint         # ESLint
npm run test         # Unit tests (vitest)
```

Backend is expected at `http://localhost:8000` — Vite proxies `/api/` requests there.

## Tech Stack

- React 19 with React Compiler (babel-plugin-react-compiler)
- TypeScript 5.9, Vite (rolldown-vite)
- Redux Toolkit + RTK Query for state & API
- Tailwind CSS 4 with @tailwindcss/vite
- shadcn/ui (new-york style) + Radix UI + Lucide icons
- React Flow (@xyflow/react) for the visual canvas
- i18next for i18n (English only), translations in `src/shared/i18n/locales/`
- Zod for validation, Framer Motion for animations
- React Router DOM 7 (createBrowserRouter)

## Architecture (Feature-Sliced Design)

Strict FSD with unidirectional dependencies: `app` → `pages` → `features` → `entities` → `shared`. Importing from a higher layer is forbidden.

```
src/
  app/        — providers, router, store, layouts (auth/main/docs)
  pages/      — one per route, compose entities & features
  features/   — reusable business features (onboarding, variable-form)
  entities/   — domain models: workflow, session, credential, billing,
                execution, knowledge-base, organization, project, etc.
  shared/     — base API, config, i18n, lib utils, UI components
```

### Slice structure (entities/features/pages)

```
<slice>/
  index.ts      ← public API, the ONLY import point for external code
  api/          ← RTK Query endpoints (*.api.ts) via baseApi.injectEndpoints()
  model/        ← types.ts, Redux slices (*.slice.ts)
  ui/           ← React components
  lib/          ← hooks (use-*.ts) and utilities
```

**Import rule:** Always import through `index.ts` barrel exports (`@/entities/workflow`), never into subfolders directly.

### Voice Agents vs Agents — naming trap

- `pages/agents` lists **workflows** (a workflow is called an "agent" in product copy).
- `pages/voice-agents` lists **voice agents** — a separate entity with no graph, backed
  by `entities/voice-agent` and the `/api/voice-agents` REST resource. A voice agent
  holds a prompt, a speech-to-speech voice, knowledge bases inlined into the prompt, and
  optional workflow references used only as background analysis hooks.

These are different entities with confusingly similar names. Check which one you are in
before editing.

### Browser audio (voice-agent test call)

- `shared/lib/use-pcm-player.ts` — streaming PCM playback, shared by the workflow debug
  panel and voice calls. Its `flush()` stops every already-scheduled source, which is what
  makes barge-in work: an `AudioBufferSourceNode` plays to the end once started, so
  dropping the schedule pointer alone leaves the agent talking over the user.
- `entities/voice-agent/lib/use-voice-call.ts` — owns a call: mints a session token, opens
  the WebSocket, streams microphone frames up and plays audio frames down.
- `public/pcm-recorder.worklet.js` — microphone capture worklet, emitting ~200 ms PCM16
  frames off the main thread. It lives in `public/` on purpose: importing it with `?url`
  makes Vite inline it as a `data:` URL, which `audioWorklet.addModule()` rejects under a
  strict CSP and on some browsers.
- Nothing resamples audio, and **the rate is not a constant** — providers disagree
  (OpenAI is 24 kHz both ways, Gemini Live listens at 16 kHz and answers at 24 kHz). The
  server names both rates in the `session.ready` frame; capture starts only after it
  arrives, in an `AudioContext` built at `inputSampleRate`, while playback runs through
  `usePcmPlayer` at `outputSampleRate`. Two contexts, one per direction, both native.
- `entities/voice-session` — call history: the list on the agent's Calls tab and the
  session page with the transcript and links into the execution viewer for every
  analysis-hook run.

### RTK Query API pattern

All endpoints use `baseApi.injectEndpoints()` from `shared/api/baseApi.ts`. New cache tag types must be registered in `baseApi`'s `tagTypes` array. Auth token, project ID, and language are injected via `prepareHeaders`.

### Redux store

Slices: `session`, `variables`, `credential`, `editorMode`, `workspace`, `onboarding` — registered in `app/store/store.ts`.

### Workflow editor

The canvas lives in `entities/workflow/lib/workflow-editor/`. Key parts:
- `ui/canvas.tsx` — main React Flow canvas
- `ui/nodes/` — visual node components (agent, condition, start, end, etc.)
- `ui/node-forms/` — configuration forms per node type
- `ui/state/` — state variable management UI
- `ui/debug/` — debug panel & execution viewer
- `model/editor-mode.slice.ts` — editor state (Redux)
- `lib/use-undo-redo.ts`, `lib/use-workflow-debug.ts`

## Key Conventions

- **All user-facing text must use i18n** — `t("key")` via `useTranslation()`, never hardcoded strings
- **Backend snake_case → frontend camelCase** — automatic conversion happens, always use camelCase in frontend code
- **File naming:** kebab-case for files, PascalCase for component names
- **Event handlers:** prefix with `handle` (e.g., `handleClick`, `handleKeyDown`)
- **Use `const` arrow functions**, not `function` declarations
- **Use early returns** for readability
- **Styling:** Tailwind classes only, no inline CSS or `<style>` tags
- **Path alias:** `@/` maps to `src/`
- **shadcn/ui config:** new-york style, utils at `@/shared/lib/utils`, UI at `@/shared/ui`
- **Do not `git push`** unless explicitly told to
