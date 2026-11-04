import { ajustarAoQuadro, ESCALA_MAXIMA, ESCALA_MINIMA, zoomEm } from "./geometria";

describe("ajustarAoQuadro", () => {
  it("encolhe o conteúdo grande até caber, com margem, e o centraliza", () => {
    const vista = ajustarAoQuadro({ largura: 1000, altura: 400 }, { largura: 600, altura: 400 }, 0);

    expect(vista.escala).toBeCloseTo(0.6);
    expect(vista.x).toBeCloseTo(0);
    expect(vista.y).toBeCloseTo((400 - 400 * 0.6) / 2);
  });

  it("nunca amplia além de 1: conteúdo pequeno fica no tamanho real, centralizado", () => {
    const vista = ajustarAoQuadro({ largura: 100, altura: 100 }, { largura: 600, altura: 400 }, 0);

    expect(vista.escala).toBe(1);
    expect(vista.x).toBe(250);
    expect(vista.y).toBe(150);
  });

  it("respeita a escala mínima em conteúdo enorme", () => {
    const vista = ajustarAoQuadro(
      { largura: 100000, altura: 100000 },
      { largura: 600, altura: 400 },
      0,
    );

    expect(vista.escala).toBe(ESCALA_MINIMA);
  });

  it("conteúdo vazio fica na escala 1 na origem", () => {
    expect(ajustarAoQuadro({ largura: 0, altura: 0 }, { largura: 600, altura: 400 }, 0)).toEqual({
      x: 0,
      y: 0,
      escala: 1,
    });
  });
});

describe("zoomEm", () => {
  it("mantém parado o ponto sob o cursor", () => {
    const antes = { x: 10, y: 20, escala: 1 };
    const cursor = { x: 200, y: 100 };
    // o ponto do conteúdo sob o cursor antes do zoom
    const sob = { x: (cursor.x - antes.x) / antes.escala, y: (cursor.y - antes.y) / antes.escala };

    const depois = zoomEm(antes, cursor, 2);

    expect(depois.escala).toBe(2);
    expect(depois.x + sob.x * depois.escala).toBeCloseTo(cursor.x);
    expect(depois.y + sob.y * depois.escala).toBeCloseTo(cursor.y);
  });

  it("não passa dos limites de escala", () => {
    const base = { x: 0, y: 0, escala: 1 };

    expect(zoomEm(base, { x: 0, y: 0 }, 100).escala).toBe(ESCALA_MAXIMA);
    expect(zoomEm(base, { x: 0, y: 0 }, 0.0001).escala).toBe(ESCALA_MINIMA);
  });
});
