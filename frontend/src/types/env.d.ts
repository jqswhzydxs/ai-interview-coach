interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_USE_MOCKS?: "true" | "false";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
