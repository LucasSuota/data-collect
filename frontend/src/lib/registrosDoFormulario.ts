import type { ClienteApi, Esquemas, Registro } from "../api/cliente";

type Coluna = Esquemas["ColunaSaida"];

export interface RegistroComColunas {
  registro: Registro;
  /** As colunas da versão em que o registro nasceu (a definição pode ter mudado depois). */
  colunas: Coluna[];
}

export interface RegistrosDoFormulario {
  registros: RegistroComColunas[];
  /** Quantos existem de verdade, contando os que não couberam no limite. */
  total: number;
  truncado: boolean;
}

/**
 * Os registros de um formulário em todas as versões. A listagem da API traz uma versão por vez,
 * e um registro antigo continua valendo (e continua podendo ser apontado por outro formulário).
 */
export async function carregarRegistrosDoFormulario(
  cliente: ClienteApi,
  formularioId: number,
  limitePorVersao: number,
): Promise<RegistrosDoFormulario> {
  const versoes = await cliente.listarVersoes(formularioId);
  const paginas = await Promise.all(
    versoes.map((versao) =>
      cliente.listarRegistros(formularioId, { versaoId: versao.id, limite: limitePorVersao }),
    ),
  );
  const registros = paginas
    .flatMap((pagina) => pagina.itens.map((registro) => ({ registro, colunas: pagina.colunas })))
    .sort((a, b) => b.registro.id - a.registro.id);
  const total = paginas.reduce((soma, pagina) => soma + pagina.total, 0);
  return { registros, total, truncado: total > registros.length };
}
