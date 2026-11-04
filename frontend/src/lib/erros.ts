import { ErroDaApi } from "../api/cliente";

/** A mensagem que o servidor mandou (já em português), ou uma frase neutra para erro inesperado. */
export function mensagemDoErro(erro: unknown, padrao = "Algo deu errado. Tente de novo."): string {
  return erro instanceof ErroDaApi ? erro.message : padrao;
}
