import { useEffect, useState } from "react";
import { ErroDaApi } from "../api/cliente";
import { Aviso } from "../ui";

export type Carga<T> =
  | { situacao: "carregando" }
  | { situacao: "erro"; mensagem: string }
  | { situacao: "pronto"; dados: T };

/** Carrega algo da API ao montar (e quando `dependencias` mudam), com cancelamento. */
export function useCarga<T>(carregar: () => Promise<T>, dependencias: unknown[]): Carga<T> {
  const [resultado, setResultado] = useState<{ deps: unknown[]; carga: Carga<T> } | null>(null);

  useEffect(() => {
    let cancelado = false;
    carregar().then(
      (dados) =>
        !cancelado && setResultado({ deps: dependencias, carga: { situacao: "pronto", dados } }),
      (erro: unknown) =>
        !cancelado &&
        setResultado({
          deps: dependencias,
          carga: { situacao: "erro", mensagem: mensagemDe(erro) },
        }),
    );
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `carregar` é recriado a cada render; só `dependencias` decidem
  }, dependencias);

  // Resultado de outras dependências (ex.: outro registro) é velho: conta como carregando.
  const vigente = resultado !== null && mesmasDependencias(resultado.deps, dependencias);
  return vigente ? resultado.carga : { situacao: "carregando" };
}

function mesmasDependencias(a: unknown[], b: unknown[]): boolean {
  return a.length === b.length && a.every((valor, i) => Object.is(valor, b[i]));
}

export function mensagemDe(erro: unknown): string {
  return erro instanceof ErroDaApi ? erro.message : "Ocorreu um erro inesperado.";
}

/**
 * A mensagem para mostrar fora de um campo: no 422 junta as mensagens por campo (são elas que
 * dizem o que está errado); nos demais erros, a mensagem do servidor.
 */
export function mensagemDetalhada(erro: unknown): string {
  if (erro instanceof ErroDaApi && erro.erros.length > 0) {
    return erro.erros.map((e) => e.mensagem).join(" ");
  }
  return mensagemDe(erro);
}

export function Falha({ mensagem }: { mensagem: string }) {
  return <Aviso tom="erro">{mensagem}</Aviso>;
}
