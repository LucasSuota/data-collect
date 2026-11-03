import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { ApiProvider } from "../api/contexto";
import type { FormularioDetalhe } from "../api/cliente";
import { clienteFalso } from "../test/clienteFalso";
import { camposDeFormulaDasReferencias, useCamposDeOrigem } from "./useCamposDeOrigem";

const FORMULARIOS = [
  { id: 1, nome: "ensaio" },
  { id: 2, nome: "proctor" },
];

function detalhe(id: number, campos: Record<string, unknown>[]): FormularioDetalhe {
  return {
    id,
    nome: "x",
    criado_em: "x",
    versao_atual: {
      id: 1,
      formulario_id: id,
      numero: 1,
      publicada_em: "x",
      definicao: { campos },
    },
  } as unknown as FormularioDetalhe;
}

const ENSAIO = detalhe(1, [
  { id: "umidade", tipo: "numero", rotulo: "Umidade", compartilhado: true },
  { id: "data", tipo: "data", rotulo: "Data", compartilhado: true },
  { id: "operador", tipo: "texto", rotulo: "Operador", compartilhado: true },
  { id: "obs", tipo: "numero", rotulo: "Obs" },
  { id: "dobro", tipo: "calculado", rotulo: "Dobro", formula: "umidade * 2", compartilhado: true },
]);

function envolver(cliente: ReturnType<typeof clienteFalso>) {
  return ({ children }: { children: ReactNode }) => (
    <ApiProvider cliente={cliente}>{children}</ApiProvider>
  );
}

describe("useCamposDeOrigem", () => {
  it("traz só os campos compartilhados que uma fórmula pode usar", async () => {
    const obterFormulario = vi.fn(async () => ENSAIO);
    const { result } = renderHook(() => useCamposDeOrigem(FORMULARIOS, ["ensaio"]), {
      wrapper: envolver(clienteFalso({ obterFormulario })),
    });

    await waitFor(() => expect(result.current["ensaio"]).toBeDefined());

    // `operador` é texto (não usável em fórmula) e `obs` não é compartilhado.
    expect(result.current["ensaio"]?.map((c) => c.id)).toEqual(["umidade", "data", "dobro"]);
    expect(obterFormulario).toHaveBeenCalledWith(1);
  });

  it("não busca de novo uma origem já carregada", async () => {
    const obterFormulario = vi.fn(async () => ENSAIO);
    const { result, rerender } = renderHook(({ nomes }) => useCamposDeOrigem(FORMULARIOS, nomes), {
      wrapper: envolver(clienteFalso({ obterFormulario })),
      initialProps: { nomes: ["ensaio"] },
    });
    await waitFor(() => expect(result.current["ensaio"]).toBeDefined());

    rerender({ nomes: ["ensaio", "ensaio"] });

    expect(obterFormulario).toHaveBeenCalledTimes(1);
  });

  it("origem que ainda não existe (por exemplo, outro rascunho) não gera busca", async () => {
    const obterFormulario = vi.fn();
    const { result } = renderHook(() => useCamposDeOrigem(FORMULARIOS, ["inexistente", ""]), {
      wrapper: envolver(clienteFalso({ obterFormulario })),
    });

    expect(result.current).toEqual({});
    expect(obterFormulario).not.toHaveBeenCalled();
  });

  it("falha ao buscar não derruba o editor: a origem fica sem campos", async () => {
    const obterFormulario = vi.fn(async () => {
      throw new Error("sem conexão");
    });
    const { result } = renderHook(() => useCamposDeOrigem(FORMULARIOS, ["proctor"]), {
      wrapper: envolver(clienteFalso({ obterFormulario })),
    });

    await waitFor(() => expect(result.current["proctor"]).toEqual([]));
  });
});

describe("camposDeFormulaDasReferencias", () => {
  it("monta `<referência>__<campo>` com o rótulo dizendo de onde vem", () => {
    const campos = camposDeFormulaDasReferencias(
      [
        { id: "ensaio", rotulo: "Ensaio", formulario: "ensaio" },
        { id: "sem_origem", rotulo: "Outro", formulario: "" },
      ],
      { ensaio: [{ id: "umidade", rotulo: "Umidade" }] },
    );

    expect(campos).toEqual([{ id: "ensaio__umidade", rotulo: "Umidade (de Ensaio)" }]);
  });

  it("origem ainda não carregada não gera campos", () => {
    expect(
      camposDeFormulaDasReferencias([{ id: "e", rotulo: "E", formulario: "ensaio" }], {}),
    ).toEqual([]);
  });
});
