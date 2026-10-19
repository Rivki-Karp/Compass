/// <reference types="vitest/config" />
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

// The API runs on FastAPI (uv run --project backend python tasks.py serve); in dev Vite proxies
// /api to it, so the browser talks to one origin and never to Anthropic. VITE_API_BASE_URL stays
// empty in dev (frontend/.env.example).
const API = process.env.COMPASS_API_URL ?? "http://127.0.0.1:8000";

/** Cloudflare Pages' _headers: the CSP's connect-src allows the backend's origin (from
 * VITE_API_BASE_URL) next to 'self', or 'self' alone when it is empty (one origin). */
function pagesHeaders(apiBaseUrl: string): Plugin {
  let outDir = "dist";
  return {
    name: "compass-pages-headers",
    apply: "build",
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir);
    },
    closeBundle() {
      // after Vite has copied public/ (with _headers) into the output
      const file = path.join(outDir, "_headers");
      const origin = apiBaseUrl ? new URL(apiBaseUrl).origin : "";
      const text = readFileSync(file, "utf-8");
      const placeholder = "connect-src 'self' __API_ORIGIN__";
      if (!text.includes(placeholder)) throw new Error(`_headers: no "${placeholder}"`);
      writeFileSync(file, text.replace(placeholder, `connect-src 'self'${origin ? ` ${origin}` : ""}`));
    },
  };
}

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    pagesHeaders(loadEnv(mode, process.cwd(), "VITE_").VITE_API_BASE_URL ?? ""),
  ],
  server: {
    port: 5173,
    proxy: { "/api": { target: API, changeOrigin: false } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"], // e2e/ is Playwright's
    css: false,
  },
}));
