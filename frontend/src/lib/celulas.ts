import type { Esquemas, Registro } from "../api/cliente";
import { formatarCelula } from "./formatacao";

type Coluna = Esquemas["ColunaSaida"];

/** Um valor de registro pronto para exibir: rótulo, texto formatado e unidade em separado. */
export interface Celula {
  id: string;
  rotulo: string;
  unidade: string | null;
  texto: string;
  /** O formulário libera este campo para os que dependem dele (§2.7). */
  compartilhado: boolean;
  /** Só para calculado booleano: `true`/`false`, ou `null` se ainda não há valor (ou há erro). */
  conforme: boolean | null;
}

/**
 * As colunas de um registro, formatadas como na listagem. Só exibição: o valor guardado mantém a
 * precisão total (AGENTS.md §7) e quem calcula é o servidor.
 */
export function celulasDoRegistro(
  registro: Registro,
  colunas: Coluna[],
  compartilhados: ReadonlySet<string>,
): Celula[] {
  return colunas.map((coluna) => ({
    id: coluna.id,
    rotulo: coluna.rotulo,
    unidade: coluna.unidade,
    texto: formatarCelula(coluna, registro.dados[coluna.id]),
    compartilhado: compartilhados.has(coluna.id),
    conforme: conformidadeDe(coluna, registro.dados[coluna.id]),
  }));
}

function conformidadeDe(coluna: Coluna, guardado: unknown): boolean | null {
  if (coluna.tipo !== "calculado" || coluna.resultado !== "booleano") return null;
  if (typeof guardado !== "object" || guardado === null) return null;
  const { valor, erro } = guardado as { valor?: unknown; erro?: unknown };
  if (typeof erro === "string") return null;
  return typeof valor === "boolean" ? valor : null;
}
