import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi } from "../api/cliente";
import { clienteFalso as clienteBase, renderizarComApi } from "../test/clienteFalso";
import type { ClienteApi } from "../api/cliente";
import { PaginaDeFormularios } from "./PaginaDeFormularios";

/** A tela sempre pede as pastas junto com os formulários; sem pastas, a lista é plana como antes. */
const clienteFalso = (sobrescritas: Partial<ClienteApi> = {}) =>
  clienteBase({ listarPastas: async () => [], ...sobrescritas });

const resumo = (id: number, nome: string, numero = 1) => ({
  id,
  nome,
  criado_em: "2026-11-02T10:00:00+00:00",
  versao_atual_id: id * 10,
  versao_atual_numero: numero,
});

describe("PaginaDeFormularios", () => {
  it("lista os formulários com a versão atual", async () => {
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({
        listarFormularios: async () => [resumo(1, "Corpo de prova", 3), resumo(2, "Inspeção")],
      }),
    );

    expect(await screen.findByText("Corpo de prova")).toBeInTheDocument();
    expect(screen.getByText("versão 3")).toBeInTheDocument();
    expect(screen.getByText("Inspeção")).toBeInTheDocument();
  });

  it("sem formulários, convida a criar o primeiro", async () => {
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({ listarFormularios: async () => [] }),
    );

    expect(await screen.findByText(/Nenhum formulário ainda/)).toBeInTheDocument();
  });

  it("mostra a falha de conexão em português", async () => {
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({
        listarFormularios: async () => {
          throw new ErroDaApi(0, "Não foi possível conectar à API.");
        },
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível conectar à API.");
  });

  it("navega para novo registro, registros, edição do formulário e construtor", async () => {
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeFormularios navegar={navegar} />,
      clienteFalso({ listarFormularios: async () => [resumo(4, "Obra")] }),
    );
    await screen.findByText("Obra");

    await userEvent.click(screen.getByRole("button", { name: "Novo registro em Obra" }));
    await userEvent.click(screen.getByRole("button", { name: "Ver registros de Obra" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar o formulário Obra" }));
    await userEvent.click(screen.getByRole("button", { name: "Novo formulário" }));

    expect(navegar.mock.calls.map(([rota]) => rota)).toEqual([
      { nome: "novoRegistro", formularioId: 4 },
      { nome: "registros", formularioId: 4 },
      { nome: "editarFormulario", formularioId: 4 },
      { nome: "novoFormulario" },
    ]);
  });

  it("exclui só depois da confirmação e recarrega a lista", async () => {
    const listarFormularios = vi
      .fn()
      .mockResolvedValueOnce([resumo(1, "Obra")])
      .mockResolvedValueOnce([]);
    const excluirFormulario = vi.fn(async () => undefined);
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({ listarFormularios, excluirFormulario }),
    );
    await screen.findByText("Obra");

    await userEvent.click(screen.getByRole("button", { name: "Excluir o formulário Obra" }));
    expect(excluirFormulario).not.toHaveBeenCalled(); // pede confirmação antes
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão de Obra" }));

    expect(excluirFormulario).toHaveBeenCalledWith(1);
    expect(await screen.findByText(/Nenhum formulário ainda/)).toBeInTheDocument();
  });

  it("mostra a mensagem do 409 quando o formulário não pode ser excluído", async () => {
    const excluirFormulario = vi.fn(async () => {
      throw new ErroDaApi(
        409,
        "O formulário 'Obra' é usado por 'Proctor' e não pode ser excluído.",
      );
    });
    renderizarComApi(
      <PaginaDeFormularios navegar={vi.fn()} />,
      clienteFalso({ listarFormularios: async () => [resumo(1, "Obra")], excluirFormulario }),
    );
    await screen.findByText("Obra");

    await userEvent.click(screen.getByRole("button", { name: "Excluir o formulário Obra" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão de Obra" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("é usado por 'Proctor'");
    expect(screen.getByText("Obra")).toBeInTheDocument(); // continua na lista
  });

  describe("duplicar", () => {
    const criada = {
      id: 2,
      nome: "Obra (cópia)",
      criado_em: "2026-11-02T10:00:00+00:00",
      versao_atual: {
        id: 20,
        formulario_id: 2,
        numero: 1,
        definicao: { campos: [] },
        publicada_em: "2026-11-02T10:00:00+00:00",
      },
    };

    it("sem digitar nome, deixa o servidor escolher e recarrega a lista com a cópia", async () => {
      const listarFormularios = vi
        .fn()
        .mockResolvedValueOnce([resumo(1, "Obra")])
        .mockResolvedValueOnce([resumo(1, "Obra"), resumo(2, "Obra (cópia)")]);
      const duplicarFormulario = vi.fn(async () => criada);
      renderizarComApi(
        <PaginaDeFormularios navegar={vi.fn()} />,
        clienteFalso({ listarFormularios, duplicarFormulario }),
      );
      await screen.findByText("Obra");

      await userEvent.click(screen.getByRole("button", { name: "Duplicar o formulário Obra" }));
      await userEvent.click(screen.getByRole("button", { name: "Criar cópia" }));

      expect(duplicarFormulario).toHaveBeenCalledWith(1, undefined);
      expect(await screen.findByText("Obra (cópia)")).toBeInTheDocument();
      expect(await screen.findByText(/Os registros não foram copiados/)).toBeInTheDocument();
    });

    it("com nome digitado, manda o nome sem as pontas em branco", async () => {
      const duplicarFormulario = vi.fn(async () => criada);
      renderizarComApi(
        <PaginaDeFormularios navegar={vi.fn()} />,
        clienteFalso({
          listarFormularios: async () => [resumo(1, "Obra")],
          duplicarFormulario,
        }),
      );
      await screen.findByText("Obra");

      await userEvent.click(screen.getByRole("button", { name: "Duplicar o formulário Obra" }));
      await userEvent.type(screen.getByLabelText("Nome da cópia"), "  Obra B  ");
      await userEvent.click(screen.getByRole("button", { name: "Criar cópia" }));

      expect(duplicarFormulario).toHaveBeenCalledWith(1, "Obra B");
    });

    it("mostra o erro de nome repetido no campo e mantém o diálogo aberto", async () => {
      const duplicarFormulario = vi.fn(async () => {
        throw new ErroDaApi(422, "Definição inválida.", [
          { campo: "nome", mensagem: "Já existe um formulário com este nome." },
        ]);
      });
      renderizarComApi(
        <PaginaDeFormularios navegar={vi.fn()} />,
        clienteFalso({
          listarFormularios: async () => [resumo(1, "Obra")],
          duplicarFormulario,
        }),
      );
      await screen.findByText("Obra");

      await userEvent.click(screen.getByRole("button", { name: "Duplicar o formulário Obra" }));
      await userEvent.type(screen.getByLabelText("Nome da cópia"), "Obra");
      await userEvent.click(screen.getByRole("button", { name: "Criar cópia" }));

      expect(await screen.findByText("Já existe um formulário com este nome.")).toBeVisible();
      expect(screen.getByLabelText("Nome da cópia")).toHaveAttribute("aria-invalid", "true");
    });

    it("cancelar fecha o diálogo sem chamar a API", async () => {
      const duplicarFormulario = vi.fn();
      renderizarComApi(
        <PaginaDeFormularios navegar={vi.fn()} />,
        clienteFalso({
          listarFormularios: async () => [resumo(1, "Obra")],
          duplicarFormulario,
        }),
      );
      await screen.findByText("Obra");

      await userEvent.click(screen.getByRole("button", { name: "Duplicar o formulário Obra" }));
      await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

      expect(screen.queryByLabelText("Nome da cópia")).not.toBeInTheDocument();
      expect(duplicarFormulario).not.toHaveBeenCalled();
    });

    it("oferece abrir a cópia no construtor", async () => {
      const navegar = vi.fn();
      renderizarComApi(
        <PaginaDeFormularios navegar={navegar} />,
        clienteFalso({
          listarFormularios: async () => [resumo(1, "Obra")],
          duplicarFormulario: async () => criada,
        }),
      );
      await screen.findByText("Obra");

      await userEvent.click(screen.getByRole("button", { name: "Duplicar o formulário Obra" }));
      await userEvent.click(screen.getByRole("button", { name: "Criar cópia" }));
      await userEvent.click(await screen.findByRole("button", { name: "Editar a cópia" }));

      expect(navegar).toHaveBeenCalledWith({ nome: "editarFormulario", formularioId: 2 });
    });
  });
});
