/**
 * Apoio à edição do texto da fórmula: só parênteses e vírgulas, para ajudar a digitar e para
 * sinalizar antes de validar. NÃO é um parser: a gramática, os tipos e o erro "oficial" são do
 * servidor (`POST /definicoes/validar`), e o front nunca decide se uma fórmula é válida.
 * Todos os índices são de unidades UTF-16 (os do `<textarea>`).
 */

const PALAVRA = /[A-Za-z0-9_]/;

export interface Pareamento {
  /** Pares [abre, fecha], na ordem em que fecham (o de dentro primeiro). */
  pares: [number, number][];
  /** Parênteses sem o seu par. */
  semPar: number[];
}

export function analisarParenteses(texto: string): Pareamento {
  const pares: [number, number][] = [];
  const abertos: number[] = [];
  const semPar: number[] = [];
  for (let i = 0; i < texto.length; i++) {
    if (texto[i] === "(") {
      abertos.push(i);
    } else if (texto[i] === ")") {
      const abre = abertos.pop();
      if (abre === undefined) semPar.push(i);
      else pares.push([abre, i]);
    }
  }
  return { pares, semPar: [...semPar, ...abertos].sort((a, b) => a - b) };
}

/** O par de parênteses ao lado do cursor (o de trás primeiro), se estiver casado. */
export function parDoCursor(texto: string, cursor: number): [number, number] | null {
  const { pares } = analisarParenteses(texto);
  for (const indice of [cursor - 1, cursor]) {
    if (texto[indice] !== "(" && texto[indice] !== ")") continue;
    const par = pares.find(([abre, fecha]) => abre === indice || fecha === indice);
    if (par) return par;
  }
  return null;
}

export interface Chamada {
  nome: string;
  /** Posição (a partir de 0) do argumento em que o cursor está. */
  argumento: number;
}

/** A função cuja lista de argumentos contém o cursor, e qual argumento é o atual. */
export function chamadaNoCursor(texto: string, cursor: number): Chamada | null {
  const antes = texto.slice(0, cursor);
  let profundidade = 0;
  for (let i = antes.length - 1; i >= 0; i--) {
    if (antes[i] === ")") profundidade++;
    else if (antes[i] === "(") {
      if (profundidade > 0) {
        profundidade--;
        continue;
      }
      const nome = nomeAntes(antes, i);
      // Parêntese sem nome na frente é só agrupamento: vale a função de fora.
      if (nome) return { nome, argumento: virgulasNoNivel(antes.slice(i + 1)) };
    }
  }
  return null;
}

function nomeAntes(texto: string, indiceDoParentese: number): string {
  let inicio = indiceDoParentese;
  while (inicio > 0 && PALAVRA.test(texto[inicio - 1] ?? "")) inicio--;
  const nome = texto.slice(inicio, indiceDoParentese);
  return /^[A-Za-z_]/.test(nome) ? nome : "";
}

function virgulasNoNivel(trecho: string): number {
  let nivel = 0;
  let virgulas = 0;
  for (const c of trecho) {
    if (c === "(") nivel++;
    else if (c === ")") nivel--;
    else if (c === "," && nivel === 0) virgulas++;
  }
  return virgulas;
}

/** Os argumentos de uma assinatura do catálogo ("se(cond, a, b)" dá ["cond", "a", "b"]). */
export function argumentosDaAssinatura(assinatura: string): string[] {
  const dentro = /\(([^)]*)\)/.exec(assinatura)?.[1];
  if (dentro === undefined) return [];
  return dentro
    .split(",")
    .map((argumento) => argumento.trim())
    .filter((argumento) => argumento !== "");
}

/** Qual argumento destacar: na função variádica (`...`), os que passam do fim caem no `...`. */
export function argumentoAtivo(argumentos: string[], indice: number): number | null {
  if (indice < argumentos.length) return indice;
  return argumentos[argumentos.length - 1] === "..." ? argumentos.length - 1 : null;
}

export interface Edicao {
  texto: string;
  cursor: number;
}

/** Tecla digitada: `null` deixa o navegador agir; senão, a edição a aplicar no lugar dela. */
export function aoDigitar(
  texto: string,
  inicio: number,
  fim: number,
  tecla: string,
): Edicao | null {
  if (inicio !== fim) return null;
  if (tecla === "(") {
    // Colado numa palavra ("soma" + "("), fecha-se à mão; o par automático é só para começar.
    if (PALAVRA.test(texto[inicio] ?? "")) return null;
    return { texto: `${texto.slice(0, inicio)}()${texto.slice(inicio)}`, cursor: inicio + 1 };
  }
  if (tecla === ")" && texto[inicio] === ")") return { texto, cursor: inicio + 1 };
  return null;
}

/** Backspace entre `(` e `)` vazios apaga os dois. */
export function aoApagar(texto: string, cursor: number): Edicao | null {
  if (texto[cursor - 1] === "(" && texto[cursor] === ")") {
    return { texto: texto.slice(0, cursor - 1) + texto.slice(cursor + 1), cursor: cursor - 1 };
  }
  return null;
}
