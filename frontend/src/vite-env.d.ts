/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The backend's public URL (frontend/.env.example); empty: the same origin. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
