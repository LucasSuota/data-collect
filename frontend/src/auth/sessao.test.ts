import { describe, expect, it } from "vitest";
import type { EquipeDaPessoa, Eu } from "../api/cliente";
import { criarSessao, escolherEquipe } from "./sessao";

function equipe(id: number, extra: Partial<EquipeDaPessoa> = {}): EquipeDaPessoa {
  return {
    id,
    nome: `Equipe ${id}`,
    ativa: false,
    cargo: { id: 1, nome: "Técnico" },
    permissoes: [],
    ...extra,
  };
}

function pessoa(equipes: EquipeDaPessoa[]): Eu {
  return { pessoa: { id: 1, nome: "Lucas", email: null }, equipes, termos_pendentes: [] };
}

describe("escolherEquipe", () => {
  it("usa a equipe lembrada neste aparelho quando a pessoa ainda pertence a ela", () => {
    const eu = pessoa([equipe(1, { ativa: true }), equipe(2)]);

    expect(escolherEquipe(eu, 2)?.id).toBe(2);
  });

  it("ignora a lembrada que não existe mais e cai na ativa", () => {
    const eu = pessoa([equipe(1), equipe(2, { ativa: true })]);

    expect(escolherEquipe(eu, 99)?.id).toBe(2);
  });

  it("cai na primeira quando nenhuma está marcada como ativa", () => {
    expect(escolherEquipe(pessoa([equipe(7), equipe(8)]), null)?.id).toBe(7);
  });

  it("devolve nulo para quem não está em nenhuma equipe", () => {
    expect(escolherEquipe(pessoa([]), null)).toBeNull();
  });
});

describe("criarSessao", () => {
  it("responde `pode` só pelas permissões da equipe ativa", () => {
    const e = equipe(1, { permissoes: ["registros:ver"] });
    const sessao = criarSessao(pessoa([e]), e, {
      trocarEquipe: () => undefined,
      recarregar: async () => undefined,
      sair: () => undefined,
    });

    expect(sessao.pode("registros:ver")).toBe(true);
    expect(sessao.pode("registros:excluir")).toBe(false);
  });
});
