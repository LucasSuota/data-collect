import { screen } from "@testing-library/react";
import { ErroDaApi } from "../api/cliente";
import { Construtor } from "../construtor/Construtor";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaDeFormularios } from "./PaginaDeFormularios";
import { PaginaDeRegistro } from "./PaginaDeRegistro";
import { PaginaDeRegistros } from "./PaginaDeRegistros";

const pendente = () => new Promise<never>(() => undefined);

describe("esqueletos de carregamento", () => {
  it("a lista de formulários mostra um esqueleto enquanto carrega", async () => {
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({ listarFormularios: pendente, listarPastas: pendente }),
    );

    expect(await screen.findByRole("status", { name: "Carregando formulários" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("a listagem de registros mostra um esqueleto da tabela enquanto carrega", async () => {
    renderizarComApi(
      <PaginaDeRegistros formularioId={1} navegar={vi.fn()} />,
      clienteFalso({
        listarRegistros: pendente,
        contagens: pendente,
        obterFormulario: pendente,
        listarVersoes: pendente,
      }),
    );

    expect(await screen.findByRole("status", { name: "Carregando registros" })).toBeInTheDocument();
  });

  it("o preenchimento de registro mostra um esqueleto do formulário enquanto carrega", async () => {
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 1 }} navegar={vi.fn()} />,
      clienteFalso({ obterFormulario: pendente }),
    );

    expect(
      await screen.findByRole("status", { name: "Carregando formulário" }),
    ).toBeInTheDocument();
  });

  it("o construtor mostra um esqueleto enquanto carrega o catálogo", async () => {
    renderizarComApi(
      <Construtor modo={{ tipo: "novo" }} navegar={vi.fn()} />,
      clienteFalso({ catalogo: pendente, listarFormularios: pendente }),
    );

    expect(
      await screen.findByRole("status", { name: "Carregando o construtor" }),
    ).toBeInTheDocument();
  });

  it("quando a carga falha, o esqueleto some e a falha aparece", async () => {
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({
        listarFormularios: async () => {
          throw new ErroDaApi(500, "Erro interno do servidor.");
        },
        listarPastas: async () => [],
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Erro interno do servidor.");
    expect(screen.queryByRole("status", { name: /Carregando/ })).not.toBeInTheDocument();
  });
});
