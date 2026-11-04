import { describe, expect, it } from "vitest";
import { barraInferior, itemAtual, itensVisiveis } from "./navegacao";

const comPermissoes = (...ids: string[]) => {
  const conjunto = new Set(ids);
  return (p: string) => conjunto.has(p);
};

const TECNICO = comPermissoes(
  "formularios:ver",
  "registros:ver",
  "registros:criar",
  "registros:editar_proprios",
);
const VISUALIZADOR = comPermissoes("formularios:ver", "registros:ver");

describe("itensVisiveis", () => {
  it("esconde Equipe, Cargos e IA de quem não tem as permissões", () => {
    const ids = itensVisiveis(TECNICO).map((i) => i.id);

    expect(ids).toEqual(["inicio", "formularios", "mapa", "registros"]);
  });

  it("mostra a administração a quem tem as permissões, pelas permissões e não pelo nome do cargo", () => {
    const ids = itensVisiveis(comPermissoes("equipe:ver", "cargos:editar")).map((i) => i.id);

    expect(ids).toEqual(["inicio", "equipe", "cargos", "ia"]);
  });

  it("quem só tem o início vê só o início", () => {
    expect(itensVisiveis(comPermissoes()).map((i) => i.id)).toEqual(["inicio"]);
  });
});

describe("barraInferior", () => {
  it("põe o botão de novo registro no meio para quem pode criar", () => {
    const tipos = barraInferior(TECNICO).map((i) => i.tipo);

    expect(tipos).toEqual(["item", "item", "novo", "item", "item"]);
  });

  it("não mostra o botão de criar ao visualizador", () => {
    expect(barraInferior(VISUALIZADOR).every((i) => i.tipo === "item")).toBe(true);
  });

  it("nunca passa de quatro destinos", () => {
    const todos = comPermissoes(
      "formularios:ver",
      "registros:ver",
      "equipe:ver",
      "registros:criar",
    );

    expect(barraInferior(todos).filter((i) => i.tipo === "item")).toHaveLength(4);
  });
});

describe("itemAtual", () => {
  it("marca Registros enquanto a pessoa edita um registro", () => {
    const itens = itensVisiveis(TECNICO);

    expect(itemAtual(itens, { nome: "registro", registroId: 3 })?.id).toBe("registros");
  });
});
