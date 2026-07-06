interface ImportMetaEnv {
  /** When `"true"`, `main.tsx` starts the MSW browser worker instead of hitting the real API. */
  readonly VITE_USE_MSW?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
