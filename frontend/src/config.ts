/**
 * Configuração em tempo de execução. No compose, o `logto-setup` escreve o `/config.json` que o
 * proxy serve (endereço do login, id do aplicativo e API resource): a mesma imagem do front serve
 * qualquer instalação. No `npm run dev` esse arquivo não existe (o Vite devolve o `index.html`),
 * então valem as variáveis `VITE_*`.
 */
export interface ConfigDoApp {
  apiBase: string;
  logto: { endpoint: string; appId: string; resource: string };
}

export class ErroDeConfiguracao extends Error {
  constructor(mensagem: string) {
    super(mensagem);
    this.name = "ErroDeConfiguracao";
  }
}

function ehConfig(valor: unknown): valor is ConfigDoApp {
  if (typeof valor !== "object" || valor === null) return false;
  const { apiBase, logto } = valor as Partial<ConfigDoApp>;
  return (
    typeof apiBase === "string" &&
    typeof logto === "object" &&
    logto !== null &&
    typeof logto.endpoint === "string" &&
    typeof logto.appId === "string" &&
    typeof logto.resource === "string"
  );
}

function configDoAmbiente(env: ImportMetaEnv): ConfigDoApp | null {
  const {
    VITE_LOGTO_ENDPOINT: endpoint,
    VITE_LOGTO_APP_ID: appId,
    VITE_LOGTO_RESOURCE: resource,
  } = env;
  if (!endpoint || !appId || !resource) return null;
  return {
    apiBase: env.VITE_API_URL || "http://localhost:8000",
    logto: { endpoint, appId, resource },
  };
}

export async function carregarConfig(
  buscar: typeof fetch = (...a) => fetch(...a),
  env: ImportMetaEnv = import.meta.env,
): Promise<ConfigDoApp> {
  try {
    const resposta = await buscar("/config.json", { cache: "no-store" });
    if (resposta.ok) {
      const corpo: unknown = await resposta.json();
      if (ehConfig(corpo)) return corpo;
    }
  } catch {
    // sem /config.json (ou HTML no lugar dele): cai nas variáveis de desenvolvimento
  }
  const doAmbiente = configDoAmbiente(env);
  if (doAmbiente) return doAmbiente;
  throw new ErroDeConfiguracao(
    "O app não está configurado: falta o /config.json (no compose, o serviço logto-setup o gera) " +
      "ou as variáveis VITE_LOGTO_ENDPOINT, VITE_LOGTO_APP_ID e VITE_LOGTO_RESOURCE.",
  );
}
