import { defineConfig, loadEnv, type Plugin, type Connect } from "vite";
import type { ServerResponse } from "http";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { htmlI18nPlugin } from "./vite-plugin-html-i18n";

// https://vite.dev/config/
// Single source of truth for env is the repo-root `.env` (one dir up).
const envDir = path.resolve(__dirname, "..");

// Redirect the bare /docs to /docs/ in dev (mirrors the prod nginx rule), so
// MkDocs' relative asset URLs resolve under /docs/ instead of the site root.
const docsTrailingSlash: Plugin = {
  name: "docs-trailing-slash",
  configureServer(server) {
    server.middlewares.use(
      (req: Connect.IncomingMessage, res: ServerResponse, next: Connect.NextFunction) => {
        if (req.url === "/docs") {
          res.statusCode = 301;
          res.setHeader("Location", "/docs/");
          res.end();
          return;
        }
        next();
      },
    );
  },
};

export default defineConfig(({ mode }) => {
  // Загружаем переменные окружения из корневого .env (envDir = корень репозитория)
  const env = loadEnv(mode, envDir, "");
  const defaultLang = (env.VITE_LANGS || "en").split(",")[0];
  // Dev API proxy target. Host default; the dev Docker stack sets this to the
  // in-network api service (http://api:8000). Not VITE_-prefixed → never bundled.
  const proxyTarget = env.DEV_PROXY_TARGET || "http://localhost:8000";
  // Dev docs proxy target. The dev Docker stack sets this to the in-network
  // docs service (http://docs:80); on the host it points at a local mkdocs.
  const docsTarget = env.DEV_DOCS_TARGET || "http://localhost:8081";

  return {
    envDir,
    plugins: [
      docsTrailingSlash,
      htmlI18nPlugin(defaultLang),
      react({
        babel: {
          plugins: [["babel-plugin-react-compiler"]],
        },
      }),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    define: {
      __AVAILABLE_LANGS__: JSON.stringify((env.VITE_LANGS || "en").split(",")),
      __DEFAULT_LANG__: JSON.stringify((env.VITE_LANGS || "en").split(",")[0]),
    },
    server: {
      proxy: {
        "/api/": {
          target: proxyTarget,
          changeOrigin: true,
        },
        // Docs (MkDocs). Match only /docs/… (with slash) so the bare /docs is
        // left for the docsTrailingSlash redirect above; strip the /docs prefix
        // so the upstream mkdocs server sees root paths. ws:true keeps
        // live-reload working through the proxy.
        "/docs/": {
          target: docsTarget,
          changeOrigin: true,
          ws: true,
          rewrite: (p) => p.replace(/^\/docs/, ""),
        },
      },
    },
  };
});
