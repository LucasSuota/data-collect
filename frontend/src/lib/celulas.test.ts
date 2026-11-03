import type { Esquemas, Registro } from "../api/cliente";
import { celulasDoRegistro } from "./celulas";

type Coluna = Esquemas["ColunaSaida"];

const coluna = (parcial: Partial<Coluna> & Pick<Coluna, "id" | "tipo">): Coluna => ({
  rotulo: parcial.id,
  unidade: null,
  casas_decimais: null,
  resultado: null,
  opcoes: [],
  filtravel: false,
  ...parcial,
});

const registro = (dados: Record<string, unknown>): Registro => ({
  id: 3,
  formulario_id: 1,
  versao_id: 1,
  dados,
  criado_em: "2026-11-02T10:00:00+00:00",
  atualizado_em: "2026-11-02T10:00:00+00:00",
});

describe("celulasDoRegistro", () => {
  it("formata o valor, mantém a unidade e o rótulo de cada coluna", () => {
    const celulas = celulasDoRegistro(
      registro({ umidade: "12.4567" }),
      [
        coluna({
          id: "umidade",
          tipo: "numero",
          rotulo: "Umidade",
          unidade: "%",
          casas_decimais: 1,
        }),
      ],
      new Set(),
    );

    expect(celulas).toEqual([
      {
        id: "umidade",
        rotulo: "Umidade",
        unidade: "%",
        texto: "12,5",
        compartilhado: false,
        conforme: null,
      },
    ]);
  });

  it("marca os campos que o formulário libera para os dependentes", () => {
    const celulas = celulasDoRegistro(
      registro({ a: "1", b: "2" }),
      [coluna({ id: "a", tipo: "numero" }), coluna({ id: "b", tipo: "numero" })],
      new Set(["b"]),
    );

    expect(celulas.map((c) => [c.id, c.compartilhado])).toEqual([
      ["a", false],
      ["b", true],
    ]);
  });

  it("calculado booleano vira conformidade: verdadeiro, falso ou ainda sem valor", () => {
    const colunas = [coluna({ id: "ok", tipo: "calculado", resultado: "booleano" })];

    const celulasDe = (dados: Record<string, unknown>) =>
      celulasDoRegistro(registro(dados), colunas, new Set()).map((c) => c.conforme);

    expect(celulasDe({ ok: { valor: true, erro: null } })).toEqual([true]);
    expect(celulasDe({ ok: { valor: false, erro: null } })).toEqual([false]);
    expect(celulasDe({ ok: { valor: null, erro: null } })).toEqual([null]);
  });

  it("calculado com erro mostra o erro no texto, sem conformidade", () => {
    const [celula] = celulasDoRegistro(
      registro({ ok: { valor: null, erro: "Divisão por zero." } }),
      [coluna({ id: "ok", tipo: "calculado", resultado: "booleano" })],
      new Set(),
    );

    expect(celula?.texto).toBe("ERRO: Divisão por zero.");
    expect(celula?.conforme).toBeNull();
  });

  it("foto mostra a quantidade e localização, o ponto", () => {
    const celulas = celulasDoRegistro(
      registro({ fotos: ["a", "b"], local: { latitude: "-23.5", longitude: "-46.6" } }),
      [coluna({ id: "fotos", tipo: "foto" }), coluna({ id: "local", tipo: "localizacao" })],
      new Set(),
    );

    expect(celulas.map((c) => c.texto)).toEqual(["2 foto(s)", "-23,5 / -46,6"]);
  });
});
