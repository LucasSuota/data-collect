import { useApi } from "../api/contexto";
import type { Definicao, Registro } from "../api/cliente";
import { useCarga, type Carga } from "../paginas/Estado";
import type { ModoDoRegistro } from "./contexto";

export interface RegistroCarregado {
  formularioId: number;
  versaoId: number;
  numeroDaVersao: number;
  nomeDoFormulario: string;
  definicao: Definicao;
  registro: Registro | null;
}

export const chaveDoModo = (modo: ModoDoRegistro) =>
  modo.tipo === "novo" ? `novo-${modo.formularioId}` : `editar-${modo.registroId}`;

/** Carrega a definição certa para o modo: a versão ATUAL num registro novo, a de ORIGEM num existente. */
export function useRegistroCarregado(modo: ModoDoRegistro): Carga<RegistroCarregado> {
  const cliente = useApi();
  return useCarga<RegistroCarregado>(async () => {
    if (modo.tipo === "novo") {
      // Registro novo: sempre a versão ATUAL, e é o `versao_id` dela que vai no POST.
      const formulario = await cliente.obterFormulario(modo.formularioId);
      return {
        formularioId: formulario.id,
        versaoId: formulario.versao_atual.id,
        numeroDaVersao: formulario.versao_atual.numero,
        nomeDoFormulario: formulario.nome,
        definicao: formulario.versao_atual.definicao,
        registro: null,
      };
    }
    // Registro existente: a definição é a da VERSÃO DELE, não a atual.
    const registro = await cliente.obterRegistro(modo.registroId);
    const [formulario, versao] = await Promise.all([
      cliente.obterFormulario(registro.formulario_id),
      cliente.obterVersao(registro.formulario_id, registro.versao_id),
    ]);
    return {
      formularioId: registro.formulario_id,
      versaoId: versao.id,
      numeroDaVersao: versao.numero,
      nomeDoFormulario: formulario.nome,
      definicao: versao.definicao,
      registro,
    };
  }, [cliente, chaveDoModo(modo)]);
}
