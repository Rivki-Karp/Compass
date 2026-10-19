/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs on FastAPI (uv run --project backend python tasks.py serve); in dev Vite proxies
// /api to it, so the browser talks to one origin and never to Anthropic. VITE_API_BASE_URL stays
// empty in dev (frontend/.env.example). Deployed, the static site's headers (the CSP among them)
// are set in render.yaml.
const API = process.env.COMPASS_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Fonts are always files, never data: URIs: the CSP's font-src is 'self' (render.yaml), and
    // the small @fontsource subsets would otherwise be inlined. Other assets: Vite's default.
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf|eot)$/i.test(file) ? false : undefined),
  },
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
});
