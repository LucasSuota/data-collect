/** Geometria do quadro do mapa: ajustar à tela e zoom ancorado no cursor. Funções puras. */
export interface Vista {
  /** Deslocamento do conteúdo, em pixels da tela. */
  x: number;
  y: number;
  escala: number;
}

export const ESCALA_MINIMA = 0.25;
export const ESCALA_MAXIMA = 2;

const limitar = (escala: number) => Math.min(ESCALA_MAXIMA, Math.max(ESCALA_MINIMA, escala));

/** Escala para o conteúdo caber (sem ampliar além do tamanho real) e posição para centralizá-lo. */
export function ajustarAoQuadro(
  conteudo: { largura: number; altura: number },
  quadro: { largura: number; altura: number },
  margem = 48,
): Vista {
  if (conteudo.largura <= 0 || conteudo.altura <= 0) return { x: 0, y: 0, escala: 1 };
  const escala = limitar(
    Math.min(
      1,
      (quadro.largura - 2 * margem) / conteudo.largura,
      (quadro.altura - 2 * margem) / conteudo.altura,
    ),
  );
  return {
    escala,
    x: (quadro.largura - conteudo.largura * escala) / 2,
    y: (quadro.altura - conteudo.altura * escala) / 2,
  };
}

/** Muda a escala por `fator` mantendo parado o ponto do conteúdo que está sob `ancora`. */
export function zoomEm(vista: Vista, ancora: { x: number; y: number }, fator: number): Vista {
  const escala = limitar(vista.escala * fator);
  const razao = escala / vista.escala;
  return {
    escala,
    x: ancora.x - (ancora.x - vista.x) * razao,
    y: ancora.y - (ancora.y - vista.y) * razao,
  };
}
