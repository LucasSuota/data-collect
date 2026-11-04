import { createContext, useContext } from "react";
import type { EquipeDaPessoa, Eu } from "../api/cliente";

/** Quem está usando o app, em que equipe e com que permissões (de `GET /eu`). */
export interface Sessao {
  eu: Eu;
  equipe: EquipeDaPessoa;
  permissoes: ReadonlySet<string>;
  /**
   * Só conveniência de interface: esconder ou bloquear um botão não protege nada, o servidor
   * confere a permissão em toda requisição (AGENTS.md §2.11, §3.3).
   */
  pode: (permissao: string) => boolean;
  trocarEquipe: (equipeId: number) => void;
  recarregar: () => Promise<void>;
  sair: () => void;
}

export const ContextoDaSessao = createContext<Sessao | null>(null);

export function useSessao(): Sessao {
  const sessao = useContext(ContextoDaSessao);
  if (!sessao) throw new Error("useSessao precisa estar dentro de uma sessão iniciada.");
  return sessao;
}

export function criarSessao(
  eu: Eu,
  equipe: EquipeDaPessoa,
  acoes: Pick<Sessao, "trocarEquipe" | "recarregar" | "sair">,
): Sessao {
  const permissoes = new Set(equipe.permissoes);
  return { eu, equipe, permissoes, pode: (p) => permissoes.has(p), ...acoes };
}

/** A equipe que vale: a lembrada neste aparelho, se a pessoa ainda estiver nela; senão a ativa. */
export function escolherEquipe(eu: Eu, lembrada: number | null): EquipeDaPessoa | null {
  return (
    eu.equipes.find((e) => e.id === lembrada) ??
    eu.equipes.find((e) => e.ativa) ??
    eu.equipes[0] ??
    null
  );
}
