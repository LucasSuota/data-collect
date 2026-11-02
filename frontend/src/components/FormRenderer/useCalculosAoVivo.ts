import { useEffect, useState } from "react";
import { useApi } from "../../api/contexto";
import type { Definicao, ErroDeCampo, ResultadoCalculado } from "../../api/cliente";
import type { Valores } from "./tipos";

export interface CalculosAoVivo {
  calculados: Record<string, ResultadoCalculado>;
  /** Erros de definição devolvidos pela prévia (a mesma lista do `validar`). */
  errosDaDefinicao: ErroDeCampo[];
  /** Falha de conexão ao pedir a prévia. */
  indisponivel: boolean;
}

const VAZIO: CalculosAoVivo = { calculados: {}, errosDaDefinicao: [], indisponivel: false };

/**
 * Pede a prévia dos campos calculados ao servidor, com debounce. O front não calcula nada:
 * a prévia usa a mesma função do salvar (AGENTS.md §2.2).
 */
export function useCalculosAoVivo(
  definicao: Definicao,
  valores: Valores,
  { habilitado = true, atrasoMs = 400 }: { habilitado?: boolean; atrasoMs?: number } = {},
): CalculosAoVivo {
  const cliente = useApi();
  const [estado, setEstado] = useState<CalculosAoVivo>(VAZIO);
  const temCalculados = definicao.campos.some((campo) => campo.tipo === "calculado");

  useEffect(() => {
    if (!habilitado || !temCalculados) return;
    let obsoleto = false;
    const temporizador = setTimeout(() => {
      cliente
        .previa(definicao, valores)
        .then((resultado) => {
          if (!obsoleto) {
            setEstado({
              calculados: resultado.calculados,
              errosDaDefinicao: resultado.erros,
              indisponivel: false,
            });
          }
        })
        .catch(() => {
          if (!obsoleto) setEstado((atual) => ({ ...atual, indisponivel: true }));
        });
    }, atrasoMs);
    return () => {
      // Uma resposta antiga não pode sobrescrever a de uma digitação mais nova.
      obsoleto = true;
      clearTimeout(temporizador);
    };
  }, [cliente, definicao, valores, habilitado, temCalculados, atrasoMs]);

  return estado;
}
