import { describe, expect, it } from "vitest";
import { lerCitacoes } from "./citacoes";

describe("lerCitacoes", () => {
  it("liga cada tipo de fonte ao lugar certo do app", () => {
    const citacoes = lerCitacoes([
      { rotulo: "Corpo de prova #3", tipo: "registro", registro_id: 3 },
      { rotulo: "Ensaio", tipo: "formulario", formulario_id: 7 },
      { rotulo: "Fórmulas", tipo: "ajuda", arquivo: "formulas.md" },
    ]);

    expect(citacoes.map((c) => c.href)).toEqual([
      "#/registros/3",
      "#/formularios/7/registros",
      "#/ajuda/formulas",
    ]);
  });

  it("não inventa link para tipo desconhecido nem para id malformado", () => {
    const citacoes = lerCitacoes([
      { rotulo: "?", tipo: "outro" },
      { rotulo: "x", tipo: "registro", registro_id: "3; drop" },
    ]);

    expect(citacoes.map((c) => c.href)).toEqual([null, null]);
  });
});
