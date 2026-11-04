import type { Campo, Esquemas, FormularioDetalhe, ResumoDeFormulario } from "../api/cliente";
import { clienteFalso } from "../test/clienteFalso";
import { carregarMapa } from "./carregarMapa";

type Coluna = Esquemas["ColunaSaida"];

const resumo = (id: number, nome: string): ResumoDeFormulario => ({
  id,
  nome,
  criado_em: "2026-11-02T10:00:00+00:00",
  versao_atual_id: id * 10,
  versao_atual_numero: 1,
  pasta_id: null,
});

const detalhe = (id: number, nome: string, campos: Campo[]): FormularioDetalhe =>
  ({
    id,
    nome,
    criado_em: "x",
    versao_atual: { id: id * 10, numero: 1, definicao: { campos } },
  }) as unknown as FormularioDetalhe;

const coluna = (id: string, tipo: Coluna["tipo"], extra: Partial<Coluna> = {}): Coluna => ({
  id,
  rotulo: id,
  tipo,
  unidade: null,
  casas_decimais: null,
  resultado: null,
  opcoes: [],
  filtravel: false,
  ...extra,
});

const registro = (id: number, formulario_id: number, dados: Record<string, unknown>) => ({
  id,
  formulario_id,
  versao_id: formulario_id * 10,
  dados,
  revisao: 1,
  criado_por: null,
  atualizado_por: null,
  criado_em: "2026-11-02T10:00:00+00:00",
  atualizado_em: "x",
});

describe("carregarMapa", () => {
  const cliente = clienteFalso({
    listarFormularios: async () => [resumo(1, "Ensaio"), resumo(2, "Proctor")],
    obterFormulario: async (id: number) =>
      id === 1
        ? detalhe(1, "Ensaio", [
            { id: "umidade", tipo: "numero", rotulo: "Umidade", compartilhado: true },
          ])
        : detalhe(2, "Proctor", [
            { id: "ensaio", tipo: "referencia", rotulo: "Ensaio", formulario: "Ensaio" },
          ]),
    listarVersoes: async (id: number) => [{ id: id * 10, numero: 1, publicada_em: "x" }],
    listarRegistros: async (id: number) =>
      id === 1
        ? {
            versao_id: 10,
            total: 1,
            colunas: [coluna("umidade", "numero", { rotulo: "Umidade", unidade: "%" })],
            exibicao: { destaque: null, status: null, resumo: [] },
            itens: [registro(5, 1, { umidade: "12.4" })],
          }
        : {
            versao_id: 20,
            total: 3,
            colunas: [coluna("ensaio", "referencia", { rotulo: "Ensaio" })],
            exibicao: { destaque: null, status: null, resumo: [] },
            itens: [registro(8, 2, { ensaio: 5 })],
          },
  });

  it("junta formulários, registros e as referências entre eles", async () => {
    const mapa = await carregarMapa(cliente, 1);

    expect(mapa.formularios.map((f) => [f.nome, f.totalDeRegistros])).toEqual([
      ["Ensaio", 1],
      ["Proctor", 3],
    ]);
    const ensaio = mapa.registros.find((r) => r.id === 5);
    expect(ensaio?.celulas).toMatchObject([
      { id: "umidade", texto: "12,4", unidade: "%", compartilhado: true },
    ]);
    expect(mapa.registros.find((r) => r.id === 8)?.referencias).toEqual([
      { campoId: "ensaio", rotulo: "Ensaio", destinoId: 5 },
    ]);
  });

  it("diz quais formulários tiveram registros cortados pelo limite", async () => {
    const mapa = await carregarMapa(cliente, 1);

    expect(mapa.truncados).toEqual(["Proctor"]);
  });

  it("referência vazia no registro não vira vínculo", async () => {
    const vazio = clienteFalso({
      ...cliente,
      listarRegistros: async () => ({
        versao_id: 20,
        total: 1,
        colunas: [coluna("ensaio", "referencia")],
        exibicao: { destaque: null, status: null, resumo: [] },
        itens: [registro(8, 2, { ensaio: null })],
      }),
    });

    const mapa = await carregarMapa(vazio, 10);

    expect(mapa.registros.every((r) => r.referencias.length === 0)).toBe(true);
  });
});
