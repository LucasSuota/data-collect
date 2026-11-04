interface ImportMetaEnv {
  /** Só no `npm run dev`: a API local (com um `/config.json` publicado, o front usa esse arquivo). */
  readonly VITE_API_URL?: string;
  readonly VITE_LOGTO_ENDPOINT?: string;
  readonly VITE_LOGTO_APP_ID?: string;
  readonly VITE_LOGTO_RESOURCE?: string;
}
