import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import { htmlI18nPlugin } from "./vite-plugin-html-i18n";

// https://vite.dev/config/
// Single source of truth for env is the repo-root `.env` (one dir up).
const envDir = path.resolve(__dirname, "..");

export default defineConfig(({ mode }) => {
  // Загружаем переменные окружения из корневого .env (envDir = корень репозитория)
  const env = loadEnv(mode, envDir, "");
  const defaultLang = (env.VITE_LANGS || "en").split(",")[0];
  // Dev API proxy target. Host default; the dev Docker stack sets this to the
  // in-network api service (http://api:8000). Not VITE_-prefixed → never bundled.
  const proxyTarget = env.DEV_PROXY_TARGET || "http://localhost:8000";

  return {
    envDir,
    plugins: [
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
      },
    },
  };
});
