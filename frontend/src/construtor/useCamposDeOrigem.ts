import { useEffect, useState } from "react";
import { useApi } from "../api/contexto";

export interface CampoDeOrigem {
  id: string;
  rotulo: string;
}

/** Tipos de campo que uma fórmula pode usar (AGENTS.md §7): texto, seleção, localização e foto, não. */
const TIPOS_USAVEIS_EM_FORMULA = ["numero", "data", "sim_nao", "calculado"];

/**
 * Os campos que cada formulário de origem **compartilha** e que uma fórmula pode usar, por nome.
 * Vêm da versão atual da origem (§2.7); a validação final (campo que a origem não compartilha,
 * por exemplo) continua sendo do servidor. Origem que não existe ainda, ou que falha ao carregar,
 * fica sem campos: o editor segue funcionando.
 */
export function useCamposDeOrigem(
  formularios: { id: number; nome: string }[],
  nomesDasOrigens: string[],
): Record<string, CampoDeOrigem[]> {
  const cliente = useApi();
  const [porNome, setPorNome] = useState<Record<string, CampoDeOrigem[]>>({});
  const chave = [...new Set(nomesDasOrigens)].join("\u0000");

  useEffect(() => {
    let cancelado = false;
    for (const nome of chave.split("\u0000")) {
      const origem = formularios.find((f) => f.nome === nome);
      if (!origem || nome in porNome) continue;
      cliente.obterFormulario(origem.id).then(
        (detalhe) => {
          const campos = detalhe.versao_atual.definicao.campos
            .filter((c) => c.compartilhado === true && TIPOS_USAVEIS_EM_FORMULA.includes(c.tipo))
            .map((c) => ({ id: c.id, rotulo: c.rotulo }));
          if (!cancelado) setPorNome((atual) => ({ ...atual, [nome]: campos }));
        },
        () => {
          if (!cancelado) setPorNome((atual) => ({ ...atual, [nome]: [] }));
        },
      );
    }
    return () => {
      cancelado = true;
    };
    // `porNome` só serve para não repetir busca; refazer o efeito a cada resposta o repetiria.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cliente, formularios, chave]);

  return porNome;
}

/** `<id da referência>__<id compartilhado>` para cada campo de referência com origem carregada. */
export function camposDeFormulaDasReferencias(
  referencias: { id: string; rotulo: string; formulario: string }[],
  origens: Record<string, CampoDeOrigem[]>,
): CampoDeOrigem[] {
  return referencias.flatMap((referencia) =>
    (origens[referencia.formulario] ?? []).map((campo) => ({
      id: `${referencia.id}__${campo.id}`,
      rotulo: `${campo.rotulo} (de ${referencia.rotulo})`,
    })),
  );
}
