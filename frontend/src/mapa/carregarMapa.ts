import type { ClienteApi } from "../api/cliente";
import { celulasDoRegistro } from "../lib/celulas";
import { carregarRegistrosDoFormulario } from "../lib/registrosDoFormulario";
import type { FormularioDoMapa, RegistroDoMapa } from "./grafo";

export interface DadosDoMapa {
  formularios: FormularioDoMapa[];
  registros: RegistroDoMapa[];
  /** Nomes dos formulários com mais registros do que o limite por versão: o mapa mostra parte. */
  truncados: string[];
}

export const LIMITE_POR_VERSAO = 200;

/**
 * Lê tudo o que o mapa mostra pelos mesmos endpoints das outras telas: o servidor continua sendo
 * a fonte dos valores (já calculados) e o front só os reúne.
 */
export async function carregarMapa(
  cliente: ClienteApi,
  limitePorVersao = LIMITE_POR_VERSAO,
): Promise<DadosDoMapa> {
  const resumos = await cliente.listarFormularios();
  const lidos = await Promise.all(
    resumos.map(async (resumo) => {
      const [detalhe, doFormulario] = await Promise.all([
        cliente.obterFormulario(resumo.id),
        carregarRegistrosDoFormulario(cliente, resumo.id, limitePorVersao),
      ]);
      return { resumo, detalhe, doFormulario };
    }),
  );

  const formularios: FormularioDoMapa[] = [];
  const registros: RegistroDoMapa[] = [];
  const truncados: string[] = [];

  for (const { resumo, detalhe, doFormulario } of lidos) {
    const definicao = detalhe.versao_atual.definicao;
    const compartilhados = new Set(
      definicao.campos.filter((campo) => campo.compartilhado === true).map((campo) => campo.id),
    );
    formularios.push({
      id: resumo.id,
      nome: resumo.nome,
      versao: resumo.versao_atual_numero,
      definicao,
      totalDeRegistros: doFormulario.total,
    });
    if (doFormulario.truncado) truncados.push(resumo.nome);

    for (const { registro, colunas } of doFormulario.registros) {
      registros.push({
        id: registro.id,
        formularioId: resumo.id,
        criadoEm: registro.criado_em,
        celulas: celulasDoRegistro(registro, colunas, compartilhados),
        referencias: colunas
          .filter((coluna) => coluna.tipo === "referencia")
          .flatMap((coluna) => {
            const destino = registro.dados[coluna.id];
            return typeof destino === "number"
              ? [{ campoId: coluna.id, rotulo: coluna.rotulo, destinoId: destino }]
              : [];
          }),
      });
    }
  }
  return { formularios, registros, truncados };
}
