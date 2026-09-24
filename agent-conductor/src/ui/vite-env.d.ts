/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CONDUCTOR_WS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
