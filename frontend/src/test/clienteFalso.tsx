import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { ApiProvider } from "../api/contexto";
import type { ClienteApi } from "../api/cliente";

/**
 * Um cliente cujos métodos falham, a menos que o teste forneça o comportamento esperado: chamada
 * que o teste não previu é bug (ou teste incompleto), nunca um `undefined` silencioso.
 */
export function clienteFalso(sobrescritas: Partial<ClienteApi> = {}): ClienteApi {
  return new Proxy(sobrescritas as ClienteApi, {
    get(alvo, nome) {
      if (typeof nome === "symbol" || nome === "then") return Reflect.get(alvo, nome);
      if (nome in alvo) return alvo[nome as keyof ClienteApi];
      return () => {
        throw new Error(`Chamada inesperada ao cliente da API: ${nome}`);
      };
    },
  });
}

export function renderizarComApi(elemento: ReactElement, cliente: ClienteApi): RenderResult {
  return render(<ApiProvider cliente={cliente}>{elemento}</ApiProvider>);
}
