import type { ArquivoBaixado, Esquemas } from "../api/cliente";
import { formatarNumero } from "./numero";

type Coluna = Esquemas["ColunaSaida"];

/**
 * Texto de uma célula da listagem a partir do valor guardado no registro. Só exibição: o valor
 * guardado mantém a precisão total; `casas_decimais` arredonda o que se vê (AGENTS.md §7).
 */
export function formatarCelula(coluna: Coluna, guardado: unknown): string {
  if (coluna.tipo === "calculado") return formatarCalculado(coluna, guardado);
  if (guardado === null || guardado === undefined) return "";
  switch (coluna.tipo) {
    case "numero":
      return formatarNumero(String(guardado), coluna.casas_decimais);
    case "sim_nao":
      return guardado === true ? "Sim" : "Não";
    case "data":
      return dataBrasileira(String(guardado));
    case "referencia":
      return `#${String(guardado)}`;
    case "localizacao":
      return formatarLocalizacao(guardado);
    default:
      return String(guardado);
  }
}

function formatarCalculado(coluna: Coluna, guardado: unknown): string {
  if (typeof guardado !== "object" || guardado === null) return "—";
  const { valor, erro } = guardado as { valor?: unknown; erro?: unknown };
  if (typeof erro === "string") return `ERRO: ${erro}`;
  if (valor === null || valor === undefined) return "—";
  if (coluna.resultado === "numero") return formatarNumero(String(valor), coluna.casas_decimais);
  if (coluna.resultado === "booleano") return valor === true ? "Sim" : "Não";
  if (coluna.resultado === "data") return dataBrasileira(String(valor));
  return String(valor);
}

/** "2026-11-02" → "02/11/2026"; qualquer outro texto volta como veio. */
export function dataBrasileira(iso: string): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? iso.split("-").reverse().join("/") : iso;
}

function formatarLocalizacao(valor: unknown): string {
  const { latitude, longitude } = valor as { latitude?: unknown; longitude?: unknown };
  if (typeof latitude !== "string" || typeof longitude !== "string") return "";
  return `${latitude} / ${longitude}`.replaceAll(".", ",");
}

/** Dispara o download padrão do navegador (no Electron, o diálogo nativo de salvar). */
export function baixarArquivo({ blob, nome }: ArquivoBaixado): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
