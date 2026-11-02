/**
 * Os blocos da fórmula: o texto dividido em **fichas léxicas** (campo, número, operador, função,
 * parênteses, vírgula). NÃO é um parser: não há gramática nem tipos aqui; quem valida e calcula é o
 * servidor (`POST /definicoes/validar`). Os blocos são sempre derivados do texto e só se reescreve o
 * texto quando a pessoa edita um bloco; o que não tem bloco (`outro`) é preservado, nunca descartado.
 */

export type TipoDeBloco =
  "campo" | "numero" | "operador" | "funcao" | "constante" | "abre" | "fecha" | "virgula" | "outro";

export interface Bloco {
  tipo: TipoDeBloco;
  texto: string;
  /** Onde começa e termina no texto, em caracteres (os mesmos offsets que o servidor devolve). */
  inicio: number;
  fim: number;
}

const NUMERO = /^(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?/;
const IDENTIFICADOR = /^[A-Za-z_][A-Za-z0-9_]*/;
const OPERADOR = /^(?:\*\*|==|!=|<=|>=|[+\-*/<>])/;
const PALAVRAS_DE_OPERADOR = ["and", "or", "not"];

/** Divide o texto em blocos. Espaços só separam; não viram bloco. */
export function lexar(texto: string, constantes: string[]): Bloco[] {
  const caracteres = Array.from(texto);
  const blocos: Bloco[] = [];
  let i = 0;

  const adicionar = (tipo: TipoDeBloco, comprimento: number) => {
    blocos.push({
      tipo,
      texto: caracteres.slice(i, i + comprimento).join(""),
      inicio: i,
      fim: i + comprimento,
    });
    i += comprimento;
  };

  while (i < caracteres.length) {
    const resto = caracteres.slice(i).join("");
    const atual = caracteres[i] ?? "";
    let achado: RegExpExecArray | null;

    if (/\s/.test(atual)) {
      i++;
    } else if ((achado = NUMERO.exec(resto))) {
      adicionar("numero", Array.from(achado[0]).length);
    } else if ((achado = IDENTIFICADOR.exec(resto))) {
      const nome = achado[0];
      const depois = resto.slice(nome.length).trimStart();
      const tipo: TipoDeBloco = PALAVRAS_DE_OPERADOR.includes(nome)
        ? "operador"
        : depois.startsWith("(")
          ? "funcao"
          : constantes.includes(nome)
            ? "constante"
            : "campo";
      adicionar(tipo, nome.length);
    } else if ((achado = OPERADOR.exec(resto))) {
      adicionar("operador", achado[0].length);
    } else if (atual === "(") {
      adicionar("abre", 1);
    } else if (atual === ")") {
      adicionar("fecha", 1);
    } else if (atual === ",") {
      adicionar("virgula", 1);
    } else {
      adicionar("outro", 1);
    }
  }
  return blocos;
}

/** O `-` é unário (negativo) no começo, depois de `(`, de vírgula ou de outro operador. */
const eMenosUnario = (blocos: Bloco[], indice: number) => {
  const bloco = blocos[indice];
  if (bloco?.tipo !== "operador" || bloco.texto !== "-") return false;
  const anterior = blocos[indice - 1];
  return (
    anterior === undefined ||
    anterior.tipo === "abre" ||
    anterior.tipo === "virgula" ||
    anterior.tipo === "operador"
  );
};

/** Junta os blocos num texto com espaçamento normal (e o mesmo conteúdo: ida e volta não perde nada). */
export function paraTexto(blocos: Bloco[]): string {
  let texto = "";
  blocos.forEach((bloco, i) => {
    const anterior = blocos[i - 1];
    const semEspaco =
      i === 0 ||
      bloco.tipo === "fecha" ||
      bloco.tipo === "virgula" ||
      anterior?.tipo === "abre" ||
      (bloco.tipo === "abre" && anterior?.tipo === "funcao") ||
      (anterior !== undefined && eMenosUnario(blocos, i - 1));
    texto += (semEspaco ? "" : " ") + bloco.texto;
  });
  return texto;
}

function renumerar(blocos: Bloco[]): Bloco[] {
  // Os deslocamentos só valem para o texto de onde os blocos vieram; depois de editar, o texto
  // novo é relexado, então aqui eles são apenas coerentes (não confiáveis).
  let posicao = 0;
  return blocos.map((bloco) => {
    const comprimento = Array.from(bloco.texto).length;
    const renumerado = { ...bloco, inicio: posicao, fim: posicao + comprimento };
    posicao += comprimento + 1;
    return renumerado;
  });
}

export function inserirBlocos(blocos: Bloco[], posicao: number, novos: Bloco[]): Bloco[] {
  const ponto = Math.max(0, Math.min(posicao, blocos.length));
  return renumerar([...blocos.slice(0, ponto), ...novos, ...blocos.slice(ponto)]);
}

export function moverBloco(blocos: Bloco[], de: number, para: number): Bloco[] {
  if (de < 0 || de >= blocos.length || de === para) return blocos;
  const destino = Math.max(0, Math.min(para, blocos.length));
  const sem = blocos.filter((_, i) => i !== de);
  return renumerar([...sem.slice(0, destino), blocos[de] as Bloco, ...sem.slice(destino)]);
}

export function removerBloco(blocos: Bloco[], indice: number): Bloco[] {
  if (indice < 0 || indice >= blocos.length) return blocos;
  return renumerar(blocos.filter((_, i) => i !== indice));
}

/** Uma função entra com os dois parênteses; `cursor` é a posição entre eles (onde vão os argumentos). */
export function blocosDaFuncao(nome: string): { blocos: Bloco[]; cursor: number } {
  const blocos = lexar(`${nome}()`, []);
  return { blocos, cursor: 2 };
}

/** Um bloco novo a partir do texto, para a paleta (campo, operador, número, constante...). */
export function blocoDe(texto: string, constantes: string[]): Bloco[] {
  return lexar(texto, constantes);
}

export interface ParesDeBlocos {
  /** Pares [abre, fecha] por posição do bloco, na ordem em que fecham. */
  pares: [number, number][];
  semPar: number[];
}

export function paresDeBlocos(blocos: Bloco[]): ParesDeBlocos {
  const pares: [number, number][] = [];
  const abertos: number[] = [];
  const semPar: number[] = [];
  blocos.forEach((bloco, i) => {
    if (bloco.tipo === "abre") abertos.push(i);
    else if (bloco.tipo === "fecha") {
      const abre = abertos.pop();
      if (abre === undefined) semPar.push(i);
      else pares.push([abre, i]);
    }
  });
  return { pares, semPar: [...semPar, ...abertos].sort((a, b) => a - b) };
}

export type Solto =
  { tipo: "inserir"; posicao: number } | { tipo: "mover"; de: number; para: number };

export const ID_DO_FIM = "bloco-fim";
export const idDoBloco = (indice: number) => `bloco-${indice}`;
export const PREFIXO_DE_ITEM = "item-";

function indiceDe(id: string): number | null {
  const achado = /^bloco-(\d+)$/.exec(id);
  return achado ? Number(achado[1]) : null;
}

/** Traduz "item ou bloco solto sobre X" na edição a fazer; `null` quando nada muda. */
export function resolverSolto(ativo: string, sobre: string | null, total: number): Solto | null {
  if (sobre === null) return null;
  const alvo = sobre === ID_DO_FIM ? total : indiceDe(sobre);
  if (alvo === null) return null;

  if (ativo.startsWith(PREFIXO_DE_ITEM)) return { tipo: "inserir", posicao: alvo };

  const de = indiceDe(ativo);
  if (de === null) return null;
  // No fim da lista, "o último lugar" é o do último bloco (o `moverBloco` já tira o movido antes).
  const para = sobre === ID_DO_FIM ? total - 1 : alvo;
  return de === para ? null : { tipo: "mover", de, para };
}
