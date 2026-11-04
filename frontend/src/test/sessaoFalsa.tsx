import type { ReactNode } from "react";
import type { EquipeDaPessoa, Eu } from "../api/cliente";
import { ContextoDaSessao, criarSessao, type Sessao } from "../auth/sessao";

/** Uma sessão pronta para os testes de tela, com o cargo e as permissões que o teste escolher. */
export function sessaoFalsa(
  permissoes: string[],
  { cargo = "Teste", nome = "Lucas Souza" }: { cargo?: string; nome?: string } = {},
): Sessao {
  const equipe: EquipeDaPessoa = {
    id: 1,
    nome: "Equipe Alfa",
    ativa: true,
    cargo: { id: 1, nome: cargo },
    permissoes,
  };
  const eu: Eu = {
    pessoa: { id: 7, nome, email: "lucas@exemplo.com" },
    equipes: [equipe],
    termos_pendentes: [],
  };
  return criarSessao(eu, equipe, {
    trocarEquipe: () => undefined,
    recarregar: async () => undefined,
    sair: () => undefined,
  });
}

export function ComSessao({ permissoes, children }: { permissoes: string[]; children: ReactNode }) {
  return (
    <ContextoDaSessao.Provider value={sessaoFalsa(permissoes)}>
      {children}
    </ContextoDaSessao.Provider>
  );
}
