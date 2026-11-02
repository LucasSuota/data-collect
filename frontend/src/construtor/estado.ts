import type { Campo, Definicao, ErroDeCampo, TipoDeCampo } from "../api/cliente";

/**
 * Um campo como o construtor o edita. `chave` é a identidade estável na tela: o `id` do campo é
 * texto que o usuário digita (e pode ficar vazio, repetido ou inválido enquanto edita), então
 * não serve de identidade. Os erros do servidor ficam presos à `chave`, por isso reordenar os
 * campos não os desloca (AGENTS.md §5.3).
 */
export interface CampoEmEdicao {
  chave: string;
  id: string;
  tipo: TipoDeCampo;
  rotulo: string;
  obrigatorio: boolean;
  unidade: string;
  casasDecimais: string;
  /** Uma opção por linha. */
  opcoes: string;
  formula: string;
  formulario: string;
  compartilhado: boolean;
  maximo: string;
}

/** Propriedades que cada tipo aceita, como o catálogo da API informa (`GET /catalogo`). */
export type PropriedadesPorTipo = Partial<Record<string, string[]>>;

export function adicionarCampo(
  campos: CampoEmEdicao[],
  tipo: TipoDeCampo,
  rotulo: string,
  gerarChave: () => string,
  posicao?: number,
): CampoEmEdicao[] {
  const novo: CampoEmEdicao = {
    chave: gerarChave(),
    id: idLivre(campos, tipo),
    tipo,
    rotulo,
    obrigatorio: false,
    unidade: "",
    casasDecimais: "",
    opcoes: "",
    formula: "",
    formulario: "",
    compartilhado: false,
    maximo: "",
  };
  const indice =
    posicao === undefined ? campos.length : Math.max(0, Math.min(posicao, campos.length));
  return [...campos.slice(0, indice), novo, ...campos.slice(indice)];
}

export function removerCampo(campos: CampoEmEdicao[], chave: string): CampoEmEdicao[] {
  return campos.filter((campo) => campo.chave !== chave);
}

export function moverCampo(
  campos: CampoEmEdicao[],
  chave: string,
  novaPosicao: number,
): CampoEmEdicao[] {
  const origem = campos.findIndex((campo) => campo.chave === chave);
  if (origem === -1) return campos;
  const restantes = campos.filter((campo) => campo.chave !== chave);
  const destino = Math.max(0, Math.min(novaPosicao, restantes.length));
  return [
    ...restantes.slice(0, destino),
    campos[origem] as CampoEmEdicao,
    ...restantes.slice(destino),
  ];
}

export function atualizarCampo(
  campos: CampoEmEdicao[],
  chave: string,
  mudancas: Partial<CampoEmEdicao>,
): CampoEmEdicao[] {
  return campos.map((campo) => (campo.chave === chave ? { ...campo, ...mudancas } : campo));
}

/**
 * A definição no formato do contrato (AGENTS.md §5.2), só com o que foi preenchido. Com
 * `aceitas`, só vão as propriedades que o tipo aceita: quem trocou número por texto não pode
 * mandar a unidade que sobrou no estado, que o servidor recusaria.
 */
export function paraDefinicao(
  campos: CampoEmEdicao[],
  aceitas?: PropriedadesPorTipo,
): { campos: Record<string, unknown>[] } {
  return {
    campos: campos.map((campo) => {
      const permitidas = aceitas?.[campo.tipo];
      const aceita = (propriedade: string) => !permitidas || permitidas.includes(propriedade);
      const saida: Record<string, unknown> = {
        id: campo.id,
        tipo: campo.tipo,
        rotulo: campo.rotulo,
      };
      if (campo.obrigatorio && aceita("obrigatorio")) saida["obrigatorio"] = true;
      if (campo.unidade.trim() && aceita("unidade")) saida["unidade"] = campo.unidade.trim();
      if (campo.casasDecimais.trim() && aceita("casas_decimais")) {
        saida["casas_decimais"] = numeroOuTexto(campo.casasDecimais);
      }
      if (campo.opcoes.trim() && aceita("opcoes")) saida["opcoes"] = linhas(campo.opcoes);
      if (campo.formula.trim() && aceita("formula")) saida["formula"] = campo.formula;
      if (campo.formulario.trim() && aceita("formulario"))
        saida["formulario"] = campo.formulario.trim();
      if (campo.compartilhado && aceita("compartilhado")) saida["compartilhado"] = true;
      if (campo.maximo.trim() && aceita("maximo")) saida["maximo"] = numeroOuTexto(campo.maximo);
      return saida;
    }),
  };
}

/** Carrega uma definição publicada para editar (nova versão). */
export function deDefinicao(definicao: Definicao, gerarChave: () => string): CampoEmEdicao[] {
  return definicao.campos.map((campo: Campo) => ({
    chave: gerarChave(),
    id: campo.id,
    tipo: campo.tipo,
    rotulo: campo.rotulo,
    obrigatorio: campo.obrigatorio ?? false,
    unidade: campo.unidade ?? "",
    casasDecimais: campo.casas_decimais == null ? "" : String(campo.casas_decimais),
    opcoes: (campo.opcoes ?? []).join("\n"),
    formula: campo.formula ?? "",
    formulario: campo.formulario ?? "",
    compartilhado: campo.compartilhado ?? false,
    maximo: campo.maximo == null ? "" : String(campo.maximo),
  }));
}

export interface ErroNoCampo {
  /** A propriedade do campo (`formula`, `casas_decimais`...); vazio quando é do campo todo. */
  propriedade: string;
  mensagem: string;
  posicao: ErroDeCampo["posicao"] | undefined;
}

export interface ErrosMapeados {
  porCampo: Record<string, ErroNoCampo[]>;
  /** O que não casa com nenhum campo da tela (por exemplo, a definição sem `campos`). */
  globais: string[];
}

/**
 * Prende cada erro do servidor ao campo da tela. `instantaneo` é o que foi enviado à validação,
 * na ordem enviada: o índice de `campos[3].id` vale para aquele envio, não para a ordem de agora.
 * Erro por `id` de campo (`resistencia.formula`) é resolvido pelo próprio `id` do envio.
 */
export function mapearErros(
  erros: ErroDeCampo[],
  instantaneo: { chave: string; id: string }[],
): ErrosMapeados {
  const porCampo: Record<string, ErroNoCampo[]> = {};
  const globais: string[] = [];

  for (const erro of erros) {
    const alvo = localizar(erro.campo, instantaneo);
    if (!alvo) {
      globais.push(erro.campo === "campos" ? erro.mensagem : `${erro.campo}: ${erro.mensagem}`);
      continue;
    }
    (porCampo[alvo.chave] ??= []).push({
      propriedade: alvo.propriedade,
      mensagem: erro.mensagem,
      posicao: erro.posicao,
    });
  }
  return { porCampo, globais };
}

function localizar(
  caminho: string,
  instantaneo: { chave: string; id: string }[],
): { chave: string; propriedade: string } | null {
  const porIndice = /^campos\[(\d+)\](?:\.(.+))?$/.exec(caminho);
  if (porIndice) {
    const alvo = instantaneo[Number(porIndice[1])];
    return alvo ? { chave: alvo.chave, propriedade: porIndice[2] ?? "" } : null;
  }
  const [id = "", ...resto] = caminho.split(".");
  const alvo = instantaneo.find((campo) => campo.id === id);
  return alvo ? { chave: alvo.chave, propriedade: resto.join(".") } : null;
}

function idLivre(campos: CampoEmEdicao[], tipo: string): string {
  const usados = new Set(campos.map((campo) => campo.id));
  for (let n = 1; ; n++) {
    const candidato = `${tipo}_${n}`;
    if (!usados.has(candidato)) return candidato;
  }
}

function linhas(texto: string): string[] {
  return texto
    .split("\n")
    .map((linha) => linha.trim())
    .filter((linha) => linha !== "");
}

function numeroOuTexto(texto: string): number | string {
  const limpo = texto.trim();
  return /^-?\d+$/.test(limpo) ? Number(limpo) : limpo;
}

/** O identificador da área de soltar da lista (soltar nela acrescenta no fim). */
export const AREA_DA_LISTA = "area-da-lista";

/** O que está sendo arrastado: um tipo da paleta ou um campo que já está na lista. */
export type Arrastado =
  { origem: "paleta"; tipo: TipoDeCampo } | { origem: "campo"; chave: string };

/**
 * Aplica um arraste-e-solta: tipo da paleta sobre um campo entra antes dele; campo sobre outro
 * campo vai para a posição do alvo; na área da lista, vai para o fim. Fora de tudo, nada muda.
 */
export function aplicarArraste(
  campos: CampoEmEdicao[],
  arrastado: Arrastado,
  alvo: string | null,
  rotulosDosTipos: Partial<Record<string, string>>,
  gerarChave: () => string,
): CampoEmEdicao[] {
  if (alvo === null) return campos;
  const posicaoDoAlvo =
    alvo === AREA_DA_LISTA ? campos.length : campos.findIndex((c) => c.chave === alvo);
  if (posicaoDoAlvo === -1) return campos;

  if (arrastado.origem === "paleta") {
    const rotulo = rotulosDosTipos[arrastado.tipo] ?? arrastado.tipo;
    return adicionarCampo(campos, arrastado.tipo, rotulo, gerarChave, posicaoDoAlvo);
  }
  if (arrastado.chave === alvo) return campos;
  // `moverCampo` tira o campo e reinsere: sobre outro campo ele assume o lugar do alvo, e na área
  // da lista (fim) o índice é o do último, já sem ele.
  const destino = alvo === AREA_DA_LISTA ? campos.length - 1 : posicaoDoAlvo;
  return moverCampo(campos, arrastado.chave, destino);
}
