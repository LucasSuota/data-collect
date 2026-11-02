import type { components } from "./esquema";

/** Tipos da API: aliases dos tipos GERADOS do OpenAPI (nunca escritos à mão, AGENTS.md §5.3). */
export type Esquemas = components["schemas"];
export type ErroDeCampo = Esquemas["ErroDeCampoSaida"];
export type ResumoDeFormulario = Esquemas["ResumoDeFormularioSaida"];
export type FormularioDetalhe = Esquemas["FormularioDetalheSaida"];
export type Versao = Esquemas["VersaoSaida"];
export type ResumoDeVersao = Esquemas["ResumoDeVersaoSaida"];
export type Definicao = Esquemas["DefinicaoSaida"];
export type Campo = Esquemas["CampoSaida"];
export type TipoDeCampo = Campo["tipo"];
export type Registro = Esquemas["RegistroSaida"];
export type ListagemDeRegistros = Esquemas["ListagemDeRegistrosSaida"];
export type ResultadoValidacao = Esquemas["ValidarSaida"];
export type ResultadoPrevia = Esquemas["PreviaSaida"];
export type ResultadoCalculado = Esquemas["ResultadoCalculadoSaida"];
export type Catalogo = Esquemas["CatalogoSaida"];
export type Anexo = Esquemas["AnexoSaida"];
export type RascunhoGerado = Esquemas["RascunhoGeradoSaida"];
export type PropostaDaIa = Esquemas["GerarSaida"];

export const CABECALHO_DO_TOKEN = "X-Forms-Token";
const URL_LOCAL_PADRAO = "http://127.0.0.1:8000";

export interface Configuracao {
  /** Vazio quando o front é servido pelo próprio backend (app instalado). */
  urlBase: string;
  token: string | null;
  fetch?: typeof fetch;
}

/** Erro uniforme da API (`{detalhe, erros}`), ou falha de conexão (`status` 0). */
export class ErroDaApi extends Error {
  readonly status: number;
  readonly erros: ErroDeCampo[];

  constructor(status: number, detalhe: string, erros: ErroDeCampo[] = []) {
    super(detalhe);
    this.name = "ErroDaApi";
    this.status = status;
    this.erros = erros;
  }

  /** As mensagens agrupadas pelo `id` do campo, para mostrar cada uma no lugar certo. */
  mensagensPorCampo(): Record<string, string[]> {
    const agrupadas: Record<string, string[]> = {};
    for (const erro of this.erros) {
      (agrupadas[erro.campo] ??= []).push(erro.mensagem);
    }
    return agrupadas;
  }
}

export interface ParametrosDeConsulta {
  versaoId?: number;
  criadoDe?: string;
  criadoAte?: string;
  /** Igualdade por campo; a API recebe `filtro=campo:valor`, repetido. */
  filtros?: Record<string, string>;
}

export interface ParametrosDeListagem extends ParametrosDeConsulta {
  limite?: number;
  deslocamento?: number;
}

export interface ArquivoBaixado {
  blob: Blob;
  nome: string;
}

/** A configuração do ambiente atual: preload do Electron, variáveis do Vite ou o padrão local. */
export function configuracaoPadrao(): Configuracao {
  const preload = window.formsApi;
  if (preload) {
    return { urlBase: preload.urlBase ?? "", token: preload.token };
  }
  return {
    urlBase: import.meta.env.VITE_API_URL || URL_LOCAL_PADRAO,
    token: import.meta.env.VITE_FORMS_TOKEN || null,
  };
}

interface Opcoes {
  corpo?: unknown;
  formulario?: FormData;
  consulta?: URLSearchParams;
}

export function criarCliente(configuracao: Configuracao) {
  const base = configuracao.urlBase.replace(/\/+$/, "");
  const chamarFetch = configuracao.fetch ?? ((...argumentos) => fetch(...argumentos));

  async function enviar(metodo: string, caminho: string, opcoes: Opcoes = {}): Promise<Response> {
    const consulta = opcoes.consulta?.toString();
    const url = `${base}${caminho}${consulta ? `?${consulta}` : ""}`;
    const cabecalhos = new Headers({ Accept: "application/json" });
    if (configuracao.token) cabecalhos.set(CABECALHO_DO_TOKEN, configuracao.token);

    let corpo: BodyInit | undefined;
    if (opcoes.formulario) {
      // Sem Content-Type: o navegador o gera com o `boundary` do multipart.
      corpo = opcoes.formulario;
    } else if (opcoes.corpo !== undefined) {
      cabecalhos.set("Content-Type", "application/json");
      corpo = JSON.stringify(opcoes.corpo);
    }

    let resposta: Response;
    try {
      resposta = await chamarFetch(url, { method: metodo, headers: cabecalhos, body: corpo });
    } catch {
      throw new ErroDaApi(
        0,
        "Não foi possível conectar à API. Verifique se o servidor está em execução.",
      );
    }
    if (!resposta.ok) throw await erroDaResposta(resposta);
    return resposta;
  }

  async function json<T>(metodo: string, caminho: string, opcoes?: Opcoes): Promise<T> {
    const resposta = await enviar(metodo, caminho, opcoes);
    return (await resposta.json()) as T;
  }

  async function semCorpo(metodo: string, caminho: string): Promise<void> {
    await enviar(metodo, caminho);
  }

  return {
    // formulários e versões
    listarFormularios: () => json<ResumoDeFormulario[]>("GET", "/formularios"),
    obterFormulario: (id: number) => json<FormularioDetalhe>("GET", `/formularios/${id}`),
    criarFormulario: (entrada: { nome: string; definicao: unknown }) =>
      json<FormularioDetalhe>("POST", "/formularios", { corpo: entrada }),
    criarFormulariosEmLote: (formularios: { nome: string; definicao: unknown }[]) =>
      json<ResumoDeFormulario[]>("POST", "/formularios/lote", { corpo: { formularios } }),
    excluirFormulario: (id: number) => semCorpo("DELETE", `/formularios/${id}`),
    listarVersoes: (formularioId: number) =>
      json<ResumoDeVersao[]>("GET", `/formularios/${formularioId}/versoes`),
    obterVersao: (formularioId: number, versaoId: number) =>
      json<Versao>("GET", `/formularios/${formularioId}/versoes/${versaoId}`),
    publicarVersao: (formularioId: number, definicao: unknown) =>
      json<Versao>("POST", `/formularios/${formularioId}/versoes`, { corpo: { definicao } }),

    // definições
    validarDefinicao: (definicao: unknown) =>
      json<ResultadoValidacao>("POST", "/definicoes/validar", { corpo: { definicao } }),
    previa: (definicao: unknown, valores: unknown) =>
      json<ResultadoPrevia>("POST", "/definicoes/previa", { corpo: { definicao, valores } }),
    catalogo: () => json<Catalogo>("GET", "/catalogo"),
    /** Propõe formulários a partir de um pedido; nunca salva nada (AGENTS.md §2.5). */
    gerarFormularios: (entrada: {
      pedido: string;
      rascunhos?: { nome: string; definicao: unknown }[];
    }) =>
      json<PropostaDaIa>("POST", "/definicoes/gerar", {
        corpo: { pedido: entrada.pedido, rascunhos: entrada.rascunhos ?? [] },
      }),

    // registros
    criarRegistro: (formularioId: number, versaoId: number, dados: unknown) =>
      json<Registro>("POST", `/formularios/${formularioId}/registros`, {
        corpo: { versao_id: versaoId, dados },
      }),
    atualizarRegistro: (registroId: number, dados: unknown) =>
      json<Registro>("PUT", `/registros/${registroId}`, { corpo: { dados } }),
    obterRegistro: (registroId: number) => json<Registro>("GET", `/registros/${registroId}`),
    excluirRegistro: (registroId: number) => semCorpo("DELETE", `/registros/${registroId}`),
    listarRegistros: (formularioId: number, parametros: ParametrosDeListagem = {}) =>
      json<ListagemDeRegistros>("GET", `/formularios/${formularioId}/registros`, {
        consulta: montarConsulta(parametros),
      }),
    exportarRegistros: async (
      formularioId: number,
      parametros: ParametrosDeConsulta = {},
    ): Promise<ArquivoBaixado> => {
      const resposta = await enviar("GET", `/formularios/${formularioId}/registros/exportar`, {
        consulta: montarConsulta(parametros),
      });
      return {
        blob: await resposta.blob(),
        nome: nomeDoArquivo(resposta.headers.get("Content-Disposition")) ?? "registros.csv",
      };
    },

    // anexos (fotos)
    enviarAnexo: (arquivo: File) => {
      const formulario = new FormData();
      formulario.append("arquivo", arquivo);
      return json<Anexo>("POST", "/anexos", { formulario });
    },
    /** A foto como Blob: um `<img src>` não consegue mandar o cabeçalho do token. */
    obterAnexo: async (anexoId: number): Promise<Blob> =>
      (await enviar("GET", `/anexos/${anexoId}`)).blob(),
  };
}

export type ClienteApi = ReturnType<typeof criarCliente>;

function montarConsulta(parametros: ParametrosDeListagem): URLSearchParams {
  const consulta = new URLSearchParams();
  if (parametros.versaoId !== undefined) consulta.set("versao_id", String(parametros.versaoId));
  if (parametros.limite !== undefined) consulta.set("limite", String(parametros.limite));
  if (parametros.deslocamento !== undefined) {
    consulta.set("deslocamento", String(parametros.deslocamento));
  }
  if (parametros.criadoDe) consulta.set("criado_de", parametros.criadoDe);
  if (parametros.criadoAte) consulta.set("criado_ate", parametros.criadoAte);
  for (const [campo, valor] of Object.entries(parametros.filtros ?? {})) {
    consulta.append("filtro", `${campo}:${valor}`);
  }
  return consulta;
}

async function erroDaResposta(resposta: Response): Promise<ErroDaApi> {
  try {
    const corpo: unknown = await resposta.json();
    if (ehErroUniforme(corpo)) {
      return new ErroDaApi(resposta.status, corpo.detalhe, corpo.erros ?? []);
    }
  } catch {
    // corpo que não é JSON (por exemplo, a página de erro de um proxy): cai na mensagem genérica
  }
  return new ErroDaApi(resposta.status, `Erro ${resposta.status} ao falar com o servidor.`);
}

function ehErroUniforme(corpo: unknown): corpo is Esquemas["ErroSaida"] {
  return (
    typeof corpo === "object" &&
    corpo !== null &&
    "detalhe" in corpo &&
    typeof (corpo as { detalhe: unknown }).detalhe === "string"
  );
}

function nomeDoArquivo(contentDisposition: string | null): string | null {
  const achado = contentDisposition?.match(/filename="([^"]+)"/);
  return achado?.[1] ?? null;
}
