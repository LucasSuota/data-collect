// O Electron (preload, com `contextBridge`) expõe só o mínimo: o token da execução e,
// se o front não for servido pelo próprio backend, a URL dele (AGENTS.md §4.1).
interface Window {
  formsApi?: { token: string; urlBase?: string };
}

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_FORMS_TOKEN?: string;
}
