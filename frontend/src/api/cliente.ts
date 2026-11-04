import type { components } from "./esquema";

/** Tipos da API: aliases dos tipos GERADOS do OpenAPI (nunca escritos à mão, AGENTS.md §5.3). */
export type Esquemas = components["schemas"];
export type ErroDeCampo = Esquemas["ErroDeCampoSaida"];
export type ResumoDeFormulario = Esquemas["ResumoDeFormularioSaida"];
export type Pasta = Esquemas["PastaSaida"];
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
export type RascunhoGerado = Esquemas["RascunhoGeradoSaida"];
export type PropostaDaIa = Esquemas["GerarSaida"];
export type Eu = Esquemas["EuSaida"];
export type EquipeDaPessoa = Esquemas["EquipeDaPessoaSaida"];
export type Membro = Esquemas["MembroSaida"];
export type Convite = Esquemas["ConviteSaida"];
export type ConviteCriado = Esquemas["ConviteCriadoSaida"];
export type Cargo = Esquemas["CargoSaida"];
export type EntradaDeCargo = Esquemas["CargoEntrada"];
export type Permissao = Esquemas["PermissaoSaida"];
export type Notificacoes = Esquemas["NotificacoesSaida"];
export type Notificacao = Esquemas["NotificacaoSaida"];
export type Progresso = Esquemas["ProgressoSaida"];
export type ConfigDaIa = Esquemas["ConfigSaida"];
export type EntradaDaConfigDaIa = Esquemas["ConfigEntrada"];
export type UsoDaIa = Esquemas["UsoSaida"];
export type Contagens = Esquemas["ContagensSaida"];
export type RegistroRecente = Esquemas["RegistroRecenteSaida"];
export type EstadoDoRegistro = RegistroRecente["estado"];
export type Busca = Esquemas["BuscaSaida"];
export type Rascunho = Esquemas["RascunhoSaida"];
export type Historico = Esquemas["HistoricoSaida"];
export type Guia = Esquemas["GuiaSaida"];
export type DocumentoLegal = Esquemas["DocumentoLegalSaida"];
export type Consentimentos = Esquemas["ConsentimentosSaida"];
export type Exemplo = Esquemas["ExemploSaida"];
export type Conversa = Esquemas["ConversaSaida"];
export type ConversaComMensagens = Esquemas["ConversaComMensagensSaida"];
export type RespostaDoAssistente = Esquemas["RespostaSaida"];
export type ResumoDaIa = Esquemas["ResumoSaida"];

export interface Configuracao {
  /** Endereço da API (ex.: `http://localhost:8000`); vazio só se o front e a API dividirem a origem. */
  urlBase: string;
  /** Token de acesso do Logto (10 minutos); o SDK o renova sozinho (AGENTS.md §2.12). */
  obterToken?: () => Promise<string | null>;
  /** Descarta o token em cache e pede outro: usado uma vez, quando o servidor diz `token_expirado`. */
  renovarToken?: () => Promise<string | null>;
  /** A equipe ativa; o servidor confere a pertença a cada requisição. */
  equipeId?: () => number | null;
  fetch?: typeof fetch;
}

/** Erro uniforme da API (`{detalhe, erros}`), ou falha de conexão (`status` 0). */
export class ErroDaApi extends Error {
  readonly status: number;
  readonly erros: ErroDeCampo[];
  /** Código estável para o front decidir o que fazer (`token_expirado`, `termos_pendentes`...). */
  readonly codigo: string | null;

  constructor(
    status: number,
    detalhe: string,
    erros: ErroDeCampo[] = [],
    codigo: string | null = null,
  ) {
    super(detalhe);
    this.name = "ErroDaApi";
    this.status = status;
    this.erros = erros;
    this.codigo = codigo;
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
  /** Só os registros que a própria pessoa criou. */
  meus?: boolean;
}

export interface ParametrosDeListagem extends ParametrosDeConsulta {
  limite?: number;
  deslocamento?: number;
}

export interface ArquivoBaixado {
  blob: Blob;
  nome: string;
}

interface Opcoes {
  corpo?: unknown;
  consulta?: URLSearchParams;
}

/** Um evento do `POST /chat` (SSE): a conversa, pedaços de texto e o fim com as citações. */
export type EventoDoChat =
  | { tipo: "conversa"; conversa_id: number }
  | { tipo: "texto"; texto: string }
  | {
      tipo: "fim";
      encontrou: boolean;
      usou_ia: boolean;
      ia_disponivel: boolean;
      citacoes: Record<string, unknown>[];
    };

export function criarCliente(configuracao: Configuracao) {
  const base = configuracao.urlBase.replace(/\/+$/, "");
  const chamarFetch = configuracao.fetch ?? ((...argumentos) => fetch(...argumentos));

  async function tentar(metodo: string, caminho: string, opcoes: Opcoes, token: string | null) {
    const consulta = opcoes.consulta?.toString();
    const url = `${base}${caminho}${consulta ? `?${consulta}` : ""}`;
    const cabecalhos = new Headers({ Accept: "application/json" });
    if (token) cabecalhos.set("Authorization", `Bearer ${token}`);
    const equipe = configuracao.equipeId?.();
    if (equipe != null) cabecalhos.set("X-Equipe", String(equipe));

    let corpo: BodyInit | undefined;
    if (opcoes.corpo !== undefined) {
      cabecalhos.set("Content-Type", "application/json");
      corpo = JSON.stringify(opcoes.corpo);
    }
    try {
      return await chamarFetch(url, { method: metodo, headers: cabecalhos, body: corpo });
    } catch {
      throw new ErroDaApi(0, "Não foi possível conectar ao servidor. Verifique sua conexão.");
    }
  }

  async function enviar(metodo: string, caminho: string, opcoes: Opcoes = {}): Promise<Response> {
    let resposta = await tentar(
      metodo,
      caminho,
      opcoes,
      (await configuracao.obterToken?.()) ?? null,
    );
    if (resposta.status === 401 && configuracao.renovarToken) {
      const erro = await erroDaResposta(resposta.clone());
      if (erro.codigo === "token_expirado") {
        // Uma renovação só, depois repete: se falhar de novo, a sessão acabou de verdade.
        const novo = await configuracao.renovarToken();
        if (novo) resposta = await tentar(metodo, caminho, opcoes, novo);
      }
    }
    if (!resposta.ok) throw await erroDaResposta(resposta);
    return resposta;
  }

  async function json<T>(metodo: string, caminho: string, opcoes?: Opcoes): Promise<T> {
    const resposta = await enviar(metodo, caminho, opcoes);
    return (await resposta.json()) as T;
  }

  async function semCorpo(metodo: string, caminho: string, corpo?: unknown): Promise<void> {
    await enviar(metodo, caminho, corpo === undefined ? {} : { corpo });
  }

  return {
    // formulários e versões
    listarFormularios: () => json<ResumoDeFormulario[]>("GET", "/formularios"),
    obterFormulario: (id: number) => json<FormularioDetalhe>("GET", `/formularios/${id}`),
    criarFormulario: (entrada: { nome: string; definicao: unknown; pasta_id?: number | null }) =>
      json<FormularioDetalhe>("POST", "/formularios", { corpo: entrada }),
    criarFormulariosEmLote: (formularios: { nome: string; definicao: unknown }[]) =>
      json<ResumoDeFormulario[]>("POST", "/formularios/lote", { corpo: { formularios } }),
    excluirFormulario: (id: number) => semCorpo("DELETE", `/formularios/${id}`),
    /** Cria uma cópia (v1 igual à versão atual, sem registros). Sem `nome`, o servidor escolhe. */
    duplicarFormulario: (id: number, nome?: string) =>
      json<FormularioDetalhe>(
        "POST",
        `/formularios/${id}/duplicar`,
        nome === undefined ? undefined : { corpo: { nome } },
      ),
    listarVersoes: (formularioId: number) =>
      json<ResumoDeVersao[]>("GET", `/formularios/${formularioId}/versoes`),
    obterVersao: (formularioId: number, versaoId: number) =>
      json<Versao>("GET", `/formularios/${formularioId}/versoes/${versaoId}`),
    publicarVersao: (formularioId: number, definicao: unknown) =>
      json<Versao>("POST", `/formularios/${formularioId}/versoes`, { corpo: { definicao } }),

    // pastas (§2.10): só organizam formulários
    listarPastas: () => json<Pasta[]>("GET", "/pastas"),
    criarPasta: (nome: string, pastaPaiId: number | null) =>
      json<Pasta>("POST", "/pastas", { corpo: { nome, pasta_pai_id: pastaPaiId } }),
    /** Renomeia e/ou move: o `PUT` substitui os dois campos. */
    atualizarPasta: (pastaId: number, nome: string, pastaPaiId: number | null) =>
      json<Pasta>("PUT", `/pastas/${pastaId}`, { corpo: { nome, pasta_pai_id: pastaPaiId } }),
    excluirPasta: (pastaId: number) => semCorpo("DELETE", `/pastas/${pastaId}`),
    /** `pastaId` nulo leva o formulário à raiz. */
    moverFormulario: (formularioId: number, pastaId: number | null) =>
      json<ResumoDeFormulario>("PUT", `/formularios/${formularioId}/pasta`, {
        corpo: { pasta_id: pastaId },
      }),

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
    /** A `revisao` é a que a tela leu: se outra pessoa salvou antes, o servidor responde 409. */
    atualizarRegistro: (registroId: number, dados: unknown, revisao: number) =>
      json<Registro>("PUT", `/registros/${registroId}`, { corpo: { dados, revisao } }),
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

    // identidade, equipe e cargos (§2.12, §2.13)
    eu: () => json<Eu>("GET", "/eu"),
    aceitarConvite: (token: string) =>
      json<Esquemas["AceitarConviteSaida"]>(
        "POST",
        `/convites/${encodeURIComponent(token)}/aceitar`,
      ),
    consentimentos: () => json<Consentimentos>("GET", "/consentimentos"),
    aceitarTermos: (documentos?: string[]) =>
      json<Consentimentos>("POST", "/consentimentos", {
        corpo: { documentos: documentos ?? null },
      }),
    sairDaEquipe: () => semCorpo("POST", "/equipe/sair"),
    renomearEquipe: (nome: string) =>
      json<Esquemas["EquipeSaida"]>("PUT", "/equipe", { corpo: { nome } }),
    listarMembros: () => json<Membro[]>("GET", "/membros"),
    trocarCargo: (usuarioId: number, cargoId: number) =>
      semCorpo("PUT", `/membros/${usuarioId}/cargo`, { cargo_id: cargoId }),
    desativarMembro: (usuarioId: number) => semCorpo("POST", `/membros/${usuarioId}/desativar`),
    reativarMembro: (usuarioId: number) => semCorpo("POST", `/membros/${usuarioId}/reativar`),
    listarConvites: () => json<Convite[]>("GET", "/convites"),
    criarConvite: (email: string, cargoId: number) =>
      json<ConviteCriado>("POST", "/convites", { corpo: { email, cargo_id: cargoId } }),
    revogarConvite: (conviteId: number) => semCorpo("DELETE", `/convites/${conviteId}`),
    listarCargos: () => json<Cargo[]>("GET", "/cargos"),
    criarCargo: (entrada: EntradaDeCargo) => json<Cargo>("POST", "/cargos", { corpo: entrada }),
    atualizarCargo: (cargoId: number, entrada: EntradaDeCargo) =>
      json<Cargo>("PUT", `/cargos/${cargoId}`, { corpo: entrada }),
    excluirCargo: (cargoId: number) => semCorpo("DELETE", `/cargos/${cargoId}`),
    catalogoDePermissoes: () =>
      json<Esquemas["CatalogoDePermissoesSaida"]>("GET", "/catalogo/permissoes"),

    // LGPD (§2.15)
    exportarMeusDados: async (): Promise<ArquivoBaixado> => {
      const resposta = await enviar("GET", "/eu/exportar");
      return {
        blob: await resposta.blob(),
        nome: nomeDoArquivo(resposta.headers.get("Content-Disposition")) ?? "meus-dados.json",
      };
    },
    excluirMinhaConta: () => semCorpo("DELETE", "/eu"),

    // início, busca e avisos (§2.18)
    registrosRecentes: (limite = 5) =>
      json<RegistroRecente[]>("GET", "/registros/recentes", {
        consulta: new URLSearchParams({ limite: String(limite) }),
      }),
    buscar: (q: string) => json<Busca>("GET", "/busca", { consulta: new URLSearchParams({ q }) }),
    notificacoes: () => json<Notificacoes>("GET", "/notificacoes"),
    marcarNotificacaoLida: (id: number) => semCorpo("POST", `/notificacoes/${id}/lida`),

    // introdução e ajuda (§2.16)
    progresso: () => json<Progresso>("GET", "/eu/onboarding"),
    salvarProgresso: (entrada: Progresso) =>
      json<Progresso>("PUT", "/eu/onboarding", { corpo: entrada }),
    exemplos: () => json<Exemplo[]>("GET", "/templates"),
    importarExemplos: (nomes: string[]) =>
      json<Esquemas["ExemplosImportadosSaida"]>("POST", "/templates/importar", {
        corpo: { nomes },
      }),
    guias: () => json<Esquemas["GuiasSaida"]>("GET", "/ajuda"),
    documentosLegais: () => json<Esquemas["DocumentosLegaisSaida"]>("GET", "/legal"),

    // rascunho de versão (§2.2) e histórico (§2.14)
    obterRascunho: (formularioId: number) =>
      json<Rascunho>("GET", `/formularios/${formularioId}/rascunho`),
    salvarRascunho: (formularioId: number, definicao: unknown, revisao?: number) =>
      json<Rascunho>("PUT", `/formularios/${formularioId}/rascunho`, {
        corpo: { definicao, revisao: revisao ?? null },
      }),
    descartarRascunho: (formularioId: number) =>
      semCorpo("DELETE", `/formularios/${formularioId}/rascunho`),
    publicarRascunho: (formularioId: number) =>
      json<Versao>("POST", `/formularios/${formularioId}/rascunho/publicar`),
    historicoDoRegistro: (registroId: number) =>
      json<Historico[]>("GET", `/registros/${registroId}/historico`),
    contagens: (formularioId: number, parametros: ParametrosDeConsulta = {}) =>
      json<Contagens>("GET", `/formularios/${formularioId}/registros/contagens`, {
        consulta: montarConsulta(parametros),
      }),

    // IA (§2.5): configuração por equipe, assistente, resumo e chat
    configDaIa: () => json<ConfigDaIa>("GET", "/ia"),
    salvarConfigDaIa: (entrada: EntradaDaConfigDaIa) =>
      json<ConfigDaIa>("PUT", "/ia", { corpo: entrada }),
    testarIa: () => json<Esquemas["TesteSaida"]>("POST", "/ia/testar"),
    reindexarIa: () => json<Esquemas["ReindexacaoSaida"]>("POST", "/ia/reindexar"),
    usoDaIa: () => json<UsoDaIa>("GET", "/ia/uso"),
    resumir: (formularioId: number, parametros: ParametrosDeConsulta = {}) =>
      json<ResumoDaIa>("POST", `/formularios/${formularioId}/resumo`, {
        consulta: montarConsulta(parametros),
      }),
    listarConversas: () => json<Conversa[]>("GET", "/chat/conversas"),
    obterConversa: (id: number) => json<ConversaComMensagens>("GET", `/chat/conversas/${id}`),
    apagarConversa: (id: number) => semCorpo("DELETE", `/chat/conversas/${id}`),
    /** Conversa por SSE: chama `aoEvento` a cada evento e resolve quando o fluxo termina. */
    conversar: async (
      entrada: { mensagem: string; conversa_id?: number | null },
      aoEvento: (evento: EventoDoChat) => void,
    ): Promise<void> => {
      const resposta = await enviar("POST", "/chat", { corpo: entrada });
      const leitor = resposta.body?.getReader();
      if (!leitor) throw new ErroDaApi(0, "O servidor não enviou a resposta.");
      const decodificador = new TextDecoder();
      let pendente = "";
      for (;;) {
        const { done, value } = await leitor.read();
        if (done) break;
        pendente += decodificador.decode(value, { stream: true });
        const quadros = pendente.split("\n\n");
        pendente = quadros.pop() ?? "";
        for (const quadro of quadros) {
          const linha = quadro.split("\n").find((l) => l.startsWith("data: "));
          if (linha) aoEvento(JSON.parse(linha.slice(6)) as EventoDoChat);
        }
      }
    },
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
  if (parametros.meus) consulta.set("meus", "true");
  for (const [campo, valor] of Object.entries(parametros.filtros ?? {})) {
    consulta.append("filtro", `${campo}:${valor}`);
  }
  return consulta;
}

async function erroDaResposta(resposta: Response): Promise<ErroDaApi> {
  try {
    const corpo: unknown = await resposta.json();
    if (ehErroUniforme(corpo)) {
      return new ErroDaApi(resposta.status, corpo.detalhe, corpo.erros ?? [], corpo.codigo ?? null);
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
