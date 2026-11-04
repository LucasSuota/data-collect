import { createContext, useContext } from "react";
import type { Registro } from "../api/cliente";

export type ModoDoRegistro =
  { tipo: "novo"; formularioId: number } | { tipo: "editar"; registroId: number };

export interface PedidoDeGaveta {
  modo: ModoDoRegistro;
  /** Chamado com o registro salvo, depois que a gaveta fecha. */
  aoConcluir: (registro: Registro) => void;
}

export interface Gavetas {
  /** Abre o editor de um registro por cima do que está na tela, sem sair dela. */
  abrir: (pedido: PedidoDeGaveta) => void;
}

export const ContextoDeGavetas = createContext<Gavetas | null>(null);

/** `null` fora do provedor (por exemplo, num `FormRenderer` isolado): quem usa esconde a ação. */
export function useGavetas(): Gavetas | null {
  return useContext(ContextoDeGavetas);
}
