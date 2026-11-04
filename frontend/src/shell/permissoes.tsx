import { useContext, useEffect, useState, type ReactNode } from "react";
import type { Permissao } from "../api/cliente";
import { useApi } from "../api/contexto";
import { ContextoDaSessao } from "../auth/sessao";
import { Icone } from "../ui";

let cache: Permissao[] | null = null;

/** O catálogo de permissões vem do servidor (é público): o front não mantém uma lista paralela. */
export function useRotulosDePermissao(): (id: string) => string {
  const api = useApi();
  const [lista, setLista] = useState<Permissao[] | null>(cache);
  useEffect(() => {
    if (cache) return;
    let ativo = true;
    api
      .catalogoDePermissoes()
      .then((r) => {
        cache = r.permissoes;
        if (ativo) setLista(r.permissoes);
      })
      .catch(() => undefined); // sem o catálogo, a frase usa o próprio id da permissão
    return () => {
      ativo = false;
    };
  }, [api]);
  return (id) => lista?.find((p) => p.id === id)?.rotulo ?? id;
}

/** Só para os testes: o cache é do módulo e vazaria entre casos. */
export function limparCacheDePermissoes() {
  cache = null;
}

/**
 * O que o cargo não pode fazer: some quando não faria sentido para ele; fica **bloqueado com
 * explicação** (borda tracejada, cadeado e a frase da permissão que falta) quando a pessoa
 * esperaria encontrá-lo (AGENTS.md §2.11). É conveniência: o servidor sempre barra (§3.3).
 */
export function Bloqueado({ permissao, children }: { permissao: string; children: ReactNode }) {
  const rotulo = useRotulosDePermissao()(permissao);
  return (
    <span className="inline-flex min-h-11 flex-col justify-center gap-0.5 rounded-controle border border-dashed border-pedra-400 px-3 py-1.5 text-sm text-pedra-600">
      <span className="inline-flex items-center gap-1.5 font-medium">
        <Icone nome="cadeado" tamanho={14} />
        {children}
      </span>
      <span className="text-xs">
        Requer a permissão “{rotulo}”. Peça à administração da equipe.
      </span>
    </span>
  );
}

/** Mostra a ação se a pessoa pode; senão, a versão bloqueada com a explicação (ou nada). */
export function ComPermissao({
  permissao,
  bloqueado,
  children,
}: {
  permissao: string;
  /** O nome da ação, para a versão bloqueada. Sem ele, a ação some. */
  bloqueado?: string;
  children: ReactNode;
}) {
  // Sem sessão (componente isolado, como nos testes) tudo fica liberado: a conveniência da tela
  // nunca substitui o servidor, que confere a permissão em toda requisição.
  const sessao = useContext(ContextoDaSessao);
  if (sessao === null || sessao.pode(permissao)) return <>{children}</>;
  return bloqueado ? <Bloqueado permissao={permissao}>{bloqueado}</Bloqueado> : null;
}
