import type { Aresta, Grafo, NoDoGrafo } from "./grafo";
import { organizar, type Medidas } from "./layout";

const no = (id: string, titulo = id): NoDoGrafo => ({
  id,
  tipo: "formulario",
  formularioId: 1,
  registroId: null,
  titulo,
  subtitulo: "",
  linhas: [],
  linhasOcultas: 0,
});
const aresta = (de: string, para: string): Aresta => ({
  id: `${de}>${para}`,
  de,
  para,
  rotulo: "",
});

const MEDIDAS: Medidas = { largura: 100, altura: () => 40, folgaX: 50, folgaY: 20 };

describe("organizar", () => {
  it("coloca a origem à esquerda e cada dependente uma coluna à frente", () => {
    const grafo: Grafo = {
      nos: [no("a"), no("b"), no("c")],
      arestas: [aresta("a", "b"), aresta("b", "c")],
    };

    const { posicoes } = organizar(grafo, MEDIDAS);

    expect(posicoes.get("a")?.x).toBe(0);
    expect(posicoes.get("b")?.x).toBe(150);
    expect(posicoes.get("c")?.x).toBe(300);
  });

  it("quem depende de dois caminhos fica depois do mais longo (diamante)", () => {
    const grafo: Grafo = {
      nos: [no("a"), no("b"), no("c"), no("d")],
      arestas: [aresta("a", "b"), aresta("b", "d"), aresta("a", "d"), aresta("a", "c")],
    };

    const { posicoes } = organizar(grafo, MEDIDAS);

    expect(posicoes.get("d")?.x).toBe(300);
    expect(posicoes.get("c")?.x).toBe(150);
  });

  it("nós da mesma coluna não se sobrepõem e a coluna fica centralizada", () => {
    const grafo: Grafo = {
      nos: [no("a"), no("b"), no("c")],
      arestas: [aresta("a", "b"), aresta("a", "c")],
    };

    const { posicoes, altura } = organizar(grafo, MEDIDAS);

    const yb = posicoes.get("b")?.y ?? NaN;
    const yc = posicoes.get("c")?.y ?? NaN;
    expect(Math.abs(yb - yc)).toBeGreaterThanOrEqual(40 + 20);
    expect(altura).toBe(100);
    // a coluna de um só nó fica no meio da coluna mais alta
    expect(posicoes.get("a")?.y).toBe(30);
  });

  it("sem vínculo, tudo na primeira coluna", () => {
    const { posicoes, largura } = organizar({ nos: [no("a"), no("b")], arestas: [] }, MEDIDAS);

    expect(posicoes.get("a")?.x).toBe(0);
    expect(posicoes.get("b")?.x).toBe(0);
    expect(largura).toBe(100);
  });

  it("ordena a coluna pela posição dos nós de origem, para as linhas cruzarem menos", () => {
    const grafo: Grafo = {
      nos: [no("a"), no("b"), no("x"), no("y")],
      // x vem de b (embaixo) e y vem de a (em cima): y deve ficar acima de x
      arestas: [aresta("b", "x"), aresta("a", "y")],
    };

    const { posicoes } = organizar(grafo, MEDIDAS);

    expect((posicoes.get("y")?.y ?? 0) < (posicoes.get("x")?.y ?? 0)).toBe(true);
  });

  it("ciclo (que o servidor não deixa publicar) não trava o layout", () => {
    const grafo: Grafo = { nos: [no("a"), no("b")], arestas: [aresta("a", "b"), aresta("b", "a")] };

    expect(() => organizar(grafo, MEDIDAS)).not.toThrow();
  });

  it("grafo vazio tem tamanho zero", () => {
    expect(organizar({ nos: [], arestas: [] }, MEDIDAS)).toMatchObject({ largura: 0, altura: 0 });
  });
});
