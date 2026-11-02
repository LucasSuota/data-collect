import { useEffect, useState } from "react";
import { ErroDaApi } from "../api/cliente";

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

export function Carregando() {
  return (
    <p role="status" className="text-slate-500">
      Carregando…
    </p>
  );
}

export function Falha({ mensagem }: { mensagem: string }) {
  return (
    <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
      {mensagem}
    </p>
  );
}
