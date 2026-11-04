import type { Campo } from "../api/cliente";
import type { DadosDoMapa } from "./carregarMapa";
import { detalheDoNo } from "./detalhe";

const campo = (c: Partial<Campo> & Pick<Campo, "id" | "tipo">): Campo => ({ rotulo: c.id, ...c });

const DADOS: DadosDoMapa = {
  truncados: [],
  formularios: [
    {
      id: 1,
      nome: "Ensaio",
      versao: 1,
      totalDeRegistros: 1,
      definicao: { campos: [campo({ id: "u", tipo: "numero", compartilhado: true })] },
    },
    {
      id: 2,
      nome: "Proctor",
      versao: 2,
      totalDeRegistros: 1,
      definicao: {
        campos: [campo({ id: "e", tipo: "referencia", rotulo: "Ensaio", formulario: "ensaio" })],
      },
    },
  ],
  registros: [
    { id: 5, formularioId: 1, criadoEm: "2026-11-02T10:00:00+00:00", celulas: [], referencias: [] },
    {
      id: 8,
      formularioId: 2,
      criadoEm: "2026-11-02T10:00:00+00:00",
      celulas: [],
      referencias: [{ campoId: "e", rotulo: "Ensaio", destinoId: 5 }],
    },
  ],
};

describe("detalheDoNo", () => {
  it("de um formulário: de quem recebe e quem o usa", () => {
    const proctor = detalheDoNo(DADOS, "formulario-2");
    const ensaio = detalheDoNo(DADOS, "formulario-1");

    expect(proctor).toMatchObject({
      tipo: "formulario",
      formulario: { nome: "Proctor" },
      recebeDe: [{ campo: "Ensaio", origem: { nome: "Ensaio" } }],
      usadoPor: [],
    });
    expect(ensaio).toMatchObject({ usadoPor: [{ nome: "Proctor" }], recebeDe: [] });
  });

  it("de um registro: as origens que ele aponta e os dependentes que o apontam", () => {
    const proctor = detalheDoNo(DADOS, "registro-8");
    const ensaio = detalheDoNo(DADOS, "registro-5");

    expect(proctor).toMatchObject({
      tipo: "registro",
      formulario: { nome: "Proctor" },
      origens: [{ rotulo: "Ensaio", registro: { id: 5 } }],
      dependentes: [],
    });
    expect(ensaio).toMatchObject({
      origens: [],
      dependentes: [{ rotulo: "Ensaio", registro: { id: 8 } }],
    });
  });

  it("nó que não existe devolve nulo", () => {
    expect(detalheDoNo(DADOS, "registro-99")).toBeNull();
    expect(detalheDoNo(DADOS, "xyz")).toBeNull();
  });
});
