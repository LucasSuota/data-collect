import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { ApiProvider } from "../api/contexto";
import type { ClienteApi } from "../api/cliente";

/** Um cliente cujos métodos falham, a menos que o teste forneça o comportamento esperado. */
export function clienteFalso(sobrescritas: Partial<ClienteApi> = {}): ClienteApi {
  const naoEsperado = (nome: string) => () => {
    throw new Error(`Chamada inesperada ao cliente da API: ${nome}`);
  };
  const nomes = [
    "listarFormularios",
    "obterFormulario",
    "criarFormulario",
    "criarFormulariosEmLote",
    "excluirFormulario",
    "duplicarFormulario",
    "listarVersoes",
    "obterVersao",
    "publicarVersao",
    "validarDefinicao",
    "previa",
    "catalogo",
    "gerarFormularios",
    "criarRegistro",
    "atualizarRegistro",
    "obterRegistro",
    "excluirRegistro",
    "listarRegistros",
    "exportarRegistros",
    "enviarAnexo",
    "obterAnexo",
  ] as const;
  const base = Object.fromEntries(nomes.map((nome) => [nome, naoEsperado(nome)]));
  return { ...base, ...sobrescritas } as unknown as ClienteApi;
}

export function renderizarComApi(elemento: ReactElement, cliente: ClienteApi): RenderResult {
  return render(<ApiProvider cliente={cliente}>{elemento}</ApiProvider>);
}
