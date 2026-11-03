import type { ReactNode } from "react";
import { Icone, type NomeDoIcone } from "./Icone";

interface Props {
  icone: NomeDoIcone;
  titulo: string;
  children?: ReactNode;
  /** A chamada para ação (um botão). */
  acao?: ReactNode;
}

/** Tela sem conteúdo ainda: diz o que é, por que está vazio e o que fazer a seguir. */
export function EstadoVazio({ icone, titulo, children, acao }: Props) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-cartao border border-dashed border-pedra-300 px-6 py-12 text-center">
      <span className="grid size-11 place-items-center rounded-full bg-pedra-100 text-pedra-500">
        <Icone nome={icone} tamanho={20} />
      </span>
      <h2 className="text-base font-semibold">{titulo}</h2>
      {children ? <p className="max-w-sm text-sm text-pedra-600">{children}</p> : null}
      {acao}
    </div>
  );
}
