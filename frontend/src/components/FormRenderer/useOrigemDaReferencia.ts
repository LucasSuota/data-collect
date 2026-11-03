import { useEffect, useState } from "react";
import { useApi } from "../../api/contexto";
import { celulasDoRegistro, type Celula } from "../../lib/celulas";
import { carregarRegistrosDoFormulario } from "../../lib/registrosDoFormulario";

export interface OpcaoDeOrigem {
  id: number;
  criadoEm: string;
  celulas: Celula[];
}

export interface Origem {
  /** `null` quando nenhum formulário tem o nome da referência. */
  formulario: { id: number; nome: string } | null;
  opcoes: OpcaoDeOrigem[];
  /** Há mais registros do que os carregados. */
  truncado: boolean;
}

export type EstadoDaOrigem =
  { situacao: "carregando" } | { situacao: "falhou" } | { situacao: "pronto"; origem: Origem };

export const LIMITE_DE_OPCOES = 200;

/**
 * Os registros do formulário de origem (achado pelo nome), de todas as versões, com os valores
 * já formatados. Ao recarregar, a tela mantém os dados anteriores em vez de piscar.
 */
export function useOrigemDaReferencia(nomeDaOrigem: string | null | undefined) {
  const cliente = useApi();
  const [estado, setEstado] = useState<EstadoDaOrigem>({ situacao: "carregando" });
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    let cancelado = false;
    async function carregar(): Promise<Origem> {
      const nome = (nomeDaOrigem ?? "").trim().toLowerCase();
      const formularios = await cliente.listarFormularios();
      const resumo = formularios.find((f) => f.nome.trim().toLowerCase() === nome);
      if (!resumo) return { formulario: null, opcoes: [], truncado: false };
      const [detalhe, lidos] = await Promise.all([
        cliente.obterFormulario(resumo.id),
        carregarRegistrosDoFormulario(cliente, resumo.id, LIMITE_DE_OPCOES),
      ]);
      const compartilhados = new Set(
        detalhe.versao_atual.definicao.campos
          .filter((campo) => campo.compartilhado === true)
          .map((campo) => campo.id),
      );
      return {
        formulario: { id: resumo.id, nome: resumo.nome },
        truncado: lidos.truncado,
        opcoes: lidos.registros.map(({ registro, colunas }) => ({
          id: registro.id,
          criadoEm: registro.criado_em,
          celulas: celulasDoRegistro(registro, colunas, compartilhados),
        })),
      };
    }
    carregar().then(
      (origem) => !cancelado && setEstado({ situacao: "pronto", origem }),
      () => !cancelado && setEstado({ situacao: "falhou" }),
    );
    return () => {
      cancelado = true;
    };
  }, [cliente, nomeDaOrigem, versao]);

  return { estado, recarregar: () => setVersao((v) => v + 1) };
}
