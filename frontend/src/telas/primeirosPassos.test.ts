import { describe, expect, it } from "vitest";
import { passosDoChecklist } from "./primeirosPassos";

const tudo = () => true;

describe("passosDoChecklist", () => {
  it("marca cada passo pelo estado real da equipe", () => {
    const passos = passosDoChecklist({ formularios: 2, registros: 0, pessoas: 1 }, tudo);

    expect(passos.map((p) => [p.id, p.feito])).toEqual([
      ["formulario", true],
      ["registro", false],
      ["convite", false],
    ]);
  });

  it("considera convidada a equipe com mais de uma pessoa", () => {
    const passos = passosDoChecklist({ formularios: 0, registros: 0, pessoas: 2 }, tudo);

    expect(passos.find((p) => p.id === "convite")?.feito).toBe(true);
  });

  it("não mostra o passo que a pessoa não tem permissão para fazer", () => {
    const soPreenche = (p: string) => p === "registros:criar";

    expect(
      passosDoChecklist({ formularios: 0, registros: 0, pessoas: 1 }, soPreenche).map((p) => p.id),
    ).toEqual(["registro"]);
  });

  it("leva a pessoa à galeria de exemplos enquanto não há formulário", () => {
    const [passo] = passosDoChecklist({ formularios: 0, registros: 0, pessoas: 1 }, tudo);

    expect(passo?.href).toBe("#/exemplos");
  });
});
