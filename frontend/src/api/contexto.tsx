import { createContext, useContext, type ReactNode } from "react";
import type { ClienteApi } from "./cliente";

const ContextoDaApi = createContext<ClienteApi | null>(null);

/** Injeta o cliente da API: os componentes não conhecem URL nem token, e os testes o trocam. */
export function ApiProvider({ cliente, children }: { cliente: ClienteApi; children: ReactNode }) {
  return <ContextoDaApi.Provider value={cliente}>{children}</ContextoDaApi.Provider>;
}

export function useApi(): ClienteApi {
  const cliente = useContext(ContextoDaApi);
  if (!cliente) throw new Error("useApi precisa estar dentro de um <ApiProvider>.");
  return cliente;
}
