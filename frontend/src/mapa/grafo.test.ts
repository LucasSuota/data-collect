import type { Campo } from "../api/cliente";
import type { Celula } from "../lib/celulas";
import {
  cadeiaDe,
  montarGrafoDeFormularios,
  montarGrafoDeRegistros,
  type FormularioDoMapa,
  type RegistroDoMapa,
} from "./grafo";

const campo = (c: Partial<Campo> & Pick<Campo, "id" | "tipo">): Campo => ({
  rotulo: c.id,
  ...c,
});

const formulario = (
  id: number,
  nome: string,
  campos: Campo[],
  registros = 0,
): FormularioDoMapa => ({
  id,
  nome,
  versao: 1,
  definicao: { campos },
  totalDeRegistros: registros,
});

const ENSAIO = formulario(
  1,
  "Ensaio",
  [
    campo({ id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%", compartilhado: true }),
    campo({ id: "obs", tipo: "texto", rotulo: "Observações" }),
  ],
  2,
);
const PROCTOR = formulario(
  2,
  "Proctor",
  [
    campo({ id: "ensaio", tipo: "referencia", rotulo: "Ensaio de origem", formulario: "ensaio" }),
    campo({ id: "gamad", tipo: "numero", rotulo: "γd máx", unidade: "g/cm³", compartilhado: true }),
  ],
  1,
);
const INSITU = formulario(
  3,
  "Insitu",
  [campo({ id: "proctor", tipo: "referencia", rotulo: "Proctor", formulario: " PROCTOR " })],
  1,
);
const SOLTO = formulario(4, "Solto", [campo({ id: "x", tipo: "texto" })]);

const celula = (id: string, texto: string, extra: Partial<Celula> = {}): Celula => ({
  id,
  rotulo: id,
  unidade: null,
  texto,
  compartilhado: false,
  conforme: null,
  ...extra,
});

const registro = (
  id: number,
  formularioId: number,
  celulas: Celula[] = [],
  referencias: RegistroDoMapa["referencias"] = [],
): RegistroDoMapa => ({
  id,
  formularioId,
  criadoEm: "2026-11-02T10:00:00+00:00",
  celulas,
  referencias,
});

describe("montarGrafoDeFormularios", () => {
  const grafo = montarGrafoDeFormularios([ENSAIO, PROCTOR, INSITU, SOLTO], {
    incluirIsolados: true,
  });

  it("liga a origem ao dependente pelo nome (sem diferenciar maiúsculas nem espaços)", () => {
    expect(grafo.arestas.map((a) => [a.de, a.para, a.rotulo])).toEqual([
      ["formulario-1", "formulario-2", "Ensaio de origem"],
      ["formulario-2", "formulario-3", "Proctor"],
    ]);
  });

  it("o nó diz o que recebe de quem e o que libera", () => {
    const proctor = grafo.nos.find((n) => n.id === "formulario-2");

    expect(proctor?.linhas).toMatchObject([
      { chave: "ensaio", tipo: "entrada", rotulo: "Ensaio de origem", valor: "Ensaio" },
      { chave: "gamad", tipo: "compartilhado", rotulo: "γd máx", valor: "g/cm³" },
    ]);
  });

  it("sem os isolados, o formulário sem vínculo não aparece", () => {
    const sem = montarGrafoDeFormularios([ENSAIO, PROCTOR, INSITU, SOLTO], {
      incluirIsolados: false,
    });

    expect(sem.nos.map((n) => n.id)).toEqual(["formulario-1", "formulario-2", "formulario-3"]);
  });

  it("se nada tem vínculo, mostra todos mesmo sem pedir os isolados", () => {
    const todos = montarGrafoDeFormularios([ENSAIO, SOLTO], { incluirIsolados: false });

    expect(todos.nos).toHaveLength(2);
    expect(todos.arestas).toEqual([]);
  });

  it("referência para um formulário que não existe não vira aresta", () => {
    const orfao = formulario(9, "Orfao", [
      campo({ id: "r", tipo: "referencia", formulario: "nao-existe" }),
    ]);

    expect(montarGrafoDeFormularios([orfao], { incluirIsolados: true }).arestas).toEqual([]);
  });
});

describe("montarGrafoDeRegistros", () => {
  const e1 = registro(1, 1, [celula("umidade", "12,4", { compartilhado: true, unidade: "%" })]);
  const e2 = registro(2, 1, [celula("umidade", "9,8", { compartilhado: true })]);
  const p1 = registro(
    10,
    2,
    [celula("gamad", "1,92", { compartilhado: true })],
    [{ campoId: "ensaio", rotulo: "Ensaio de origem", destinoId: 1 }],
  );
  const i1 = registro(
    20,
    3,
    [celula("gc", "98", { conforme: false })],
    [{ campoId: "proctor", rotulo: "Proctor", destinoId: 10 }],
  );
  const formularios = [ENSAIO, PROCTOR, INSITU];

  it("liga cada registro ao registro de origem que ele aponta", () => {
    const grafo = montarGrafoDeRegistros(formularios, [e1, e2, p1, i1], { incluirIsolados: true });

    expect(grafo.arestas.map((a) => [a.de, a.para])).toEqual([
      ["registro-1", "registro-10"],
      ["registro-10", "registro-20"],
    ]);
  });

  it("sem os isolados, o registro que ninguém aponta nem aponta ninguém some", () => {
    const grafo = montarGrafoDeRegistros(formularios, [e1, e2, p1, i1], { incluirIsolados: false });

    expect(grafo.nos.map((n) => n.id)).toEqual(["registro-1", "registro-10", "registro-20"]);
  });

  it("referência para registro que não foi carregado não vira aresta", () => {
    const grafo = montarGrafoDeRegistros(formularios, [p1], { incluirIsolados: true });

    expect(grafo.arestas).toEqual([]);
  });

  it("mostra primeiro os valores que o registro libera, depois os demais, e a conformidade", () => {
    const grafo = montarGrafoDeRegistros(
      formularios,
      [registro(5, 1, [celula("obs", "ok"), celula("umidade", "1", { compartilhado: true })])],
      { incluirIsolados: true },
    );

    expect(grafo.nos[0]?.linhas.map((l) => [l.chave, l.tipo])).toEqual([
      ["umidade", "compartilhado"],
      ["obs", "campo"],
    ]);
  });

  it("calculado booleano vira linha de conformidade", () => {
    const grafo = montarGrafoDeRegistros(formularios, [i1], { incluirIsolados: true });

    expect(grafo.nos[0]?.linhas).toMatchObject([
      { chave: "gc", tipo: "conformidade", rotulo: "gc", valor: "98", conforme: false },
    ]);
  });

  it("limita as linhas e diz quantas ficaram de fora", () => {
    const muitas = Array.from({ length: 9 }, (_, i) => celula(`c${i}`, String(i)));
    const grafo = montarGrafoDeRegistros(formularios, [registro(7, 1, muitas)], {
      incluirIsolados: true,
    });

    expect(grafo.nos[0]?.linhas).toHaveLength(6);
    expect(grafo.nos[0]?.linhasOcultas).toBe(3);
  });
});

describe("cadeiaDe", () => {
  const e1 = registro(1, 1);
  const p1 = registro(10, 2, [], [{ campoId: "ensaio", rotulo: "E", destinoId: 1 }]);
  const i1 = registro(20, 3, [], [{ campoId: "proctor", rotulo: "P", destinoId: 10 }]);
  const outro = registro(11, 2, [], [{ campoId: "ensaio", rotulo: "E", destinoId: 1 }]);
  const grafo = montarGrafoDeRegistros([ENSAIO, PROCTOR, INSITU], [e1, p1, i1, outro], {
    incluirIsolados: true,
  });

  it("do meio da cadeia, pega quem origina e quem depende, em qualquer profundidade", () => {
    const cadeia = cadeiaDe(grafo, "registro-10");

    expect([...cadeia.nos].sort()).toEqual(["registro-1", "registro-10", "registro-20"]);
    expect(cadeia.arestas).toEqual(new Set(["registro-1>registro-10", "registro-10>registro-20"]));
  });

  it("não puxa o irmão: outro dependente da mesma origem fica de fora", () => {
    expect(cadeiaDe(grafo, "registro-10").nos.has("registro-11")).toBe(false);
  });

  it("da origem, pega todos os dependentes", () => {
    expect([...cadeiaDe(grafo, "registro-1").nos].sort()).toEqual([
      "registro-1",
      "registro-10",
      "registro-11",
      "registro-20",
    ]);
  });

  it("nó que não existe devolve cadeia vazia", () => {
    expect(cadeiaDe(grafo, "registro-999").nos.size).toBe(0);
  });
});
