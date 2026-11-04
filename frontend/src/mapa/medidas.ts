import type { NoDoGrafo } from "./grafo";
import type { Medidas } from "./layout";

/**
 * Medidas fixas dos cartões: o layout e as linhas de ligação dependem delas, então o cartão
 * tem exatamente esta altura (o que não couber é cortado com reticências, não esticado).
 */
export const LARGURA_DO_NO = 280;
export const ALTURA_DO_CABECALHO = 54;
export const ALTURA_DA_LINHA = 28;
const ALTURA_DO_RODAPE = 24;
const RESPIRO = 10;

export function alturaDoNo(no: NoDoGrafo): number {
  return (
    ALTURA_DO_CABECALHO +
    no.linhas.length * ALTURA_DA_LINHA +
    (no.linhasOcultas > 0 ? ALTURA_DO_RODAPE : 0) +
    RESPIRO
  );
}

export const MEDIDAS_DO_MAPA: Medidas = {
  largura: LARGURA_DO_NO,
  altura: alturaDoNo,
  folgaX: 190,
  folgaY: 28,
};
