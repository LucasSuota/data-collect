import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi, type Definicao, type Registro } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaDeRegistro } from "./PaginaDeRegistro";

const DEFINICAO_V2: Definicao = {
  campos: [
    { id: "fck", tipo: "numero", rotulo: "fck", obrigatorio: true },
    { id: "lote", tipo: "texto", rotulo: "Lote" },
    { id: "dobro", tipo: "calculado", rotulo: "Dobro", formula: "fck * 2" },
  ],
};
const DEFINICAO_V1: Definicao = {
  campos: [
    { id: "fck", tipo: "numero", rotulo: "fck", obrigatorio: true },
    { id: "dobro", tipo: "calculado", rotulo: "Dobro", formula: "fck * 2" },
  ],
};

const formulario = (numero: number, definicao: Definicao) => ({
  id: 5,
  nome: "Corpo de prova",
  criado_em: "x",
  versao_atual: { id: 50 + numero, formulario_id: 5, numero, definicao, publicada_em: "x" },
});

const registro: Registro = {
  id: 9,
  formulario_id: 5,
  versao_id: 51,
  dados: { fck: "25", dobro: { valor: "50", erro: null } },
  criado_em: "x",
  atualizado_em: "x",
};

const previa = async () => ({ valida: true, erros: [], calculados: {} });

describe("PaginaDeRegistro: novo", () => {
  it("golden path: preenche, salva com o versao_id da versão atual e volta para a lista", async () => {
    const criarRegistro = vi.fn(async () => ({ ...registro, id: 10 }));
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={navegar} />,
      clienteFalso({
        obterFormulario: async () => formulario(2, DEFINICAO_V2),
        criarRegistro,
        previa,
      }),
    );

    await userEvent.type(await screen.findByLabelText(/fck/), "25,5");
    await userEvent.type(screen.getByLabelText("Lote"), "L-1");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() =>
      expect(navegar).toHaveBeenCalledWith({ nome: "registros", formularioId: 5 }),
    );
    // O POST leva o versao_id da versão que foi renderizada (52), e só campos de entrada.
    expect(criarRegistro).toHaveBeenCalledWith(5, 52, { fck: "25.5", lote: "L-1" });
    expect(screen.queryByText(/Dobro/)).toBeInTheDocument();
  });

  it("erro de validação: mostra cada mensagem no campo certo e não navega", async () => {
    const criarRegistro = vi.fn(async () => {
      throw new ErroDaApi(422, "Registro inválido.", [
        { campo: "fck", mensagem: "Campo obrigatório." },
        { campo: "lote", mensagem: "Deve ser um texto." },
      ]);
    });
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={navegar} />,
      clienteFalso({
        obterFormulario: async () => formulario(2, DEFINICAO_V2),
        criarRegistro,
        previa,
      }),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Salvar" }));

    expect(await screen.findByLabelText(/fck/)).toHaveAccessibleDescription("Campo obrigatório.");
    expect(screen.getByLabelText("Lote")).toHaveAccessibleDescription("Deve ser um texto.");
    expect(navegar).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Salvar" })).toBeEnabled();
  });

  it("erro que não é de um campo da tela aparece num aviso geral", async () => {
    const criarRegistro = vi.fn(async () => {
      throw new ErroDaApi(422, "Registro inválido.", [
        { campo: "fantasma", mensagem: "Este campo não existe." },
      ]);
    });
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={vi.fn()} />,
      clienteFalso({
        obterFormulario: async () => formulario(2, DEFINICAO_V2),
        criarRegistro,
        previa,
      }),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Salvar" }));

    expect(await screen.findByText(/fantasma: Este campo não existe/)).toBeInTheDocument();
  });

  it("falha de conexão ao salvar mostra o aviso e mantém o que foi digitado", async () => {
    const criarRegistro = vi.fn(async () => {
      throw new ErroDaApi(0, "Não foi possível conectar à API.");
    });
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={vi.fn()} />,
      clienteFalso({
        obterFormulario: async () => formulario(2, DEFINICAO_V2),
        criarRegistro,
        previa,
      }),
    );

    await userEvent.type(await screen.findByLabelText(/fck/), "7");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível conectar");
    expect(screen.getByLabelText(/fck/)).toHaveValue("7");
  });

  it("não deixa salvar duas vezes enquanto salva", async () => {
    let concluir: (r: Registro) => void = () => {};
    const criarRegistro = vi.fn(() => new Promise<Registro>((resolve) => (concluir = resolve)));
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={vi.fn()} />,
      clienteFalso({
        obterFormulario: async () => formulario(2, DEFINICAO_V2),
        criarRegistro,
        previa,
      }),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Salvar" }));

    expect(screen.getByRole("button", { name: "Salvando…" })).toBeDisabled();
    concluir(registro);
  });

  it("formulário inexistente mostra o erro do servidor", async () => {
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 99 }} navegar={vi.fn()} />,
      clienteFalso({
        obterFormulario: async () => {
          throw new ErroDaApi(404, "Formulário 99 não encontrado.");
        },
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Formulário 99 não encontrado.");
  });
});

describe("PaginaDeRegistro: editar", () => {
  function clienteDeEdicao(extra: Parameters<typeof clienteFalso>[0] = {}) {
    return clienteFalso({
      obterRegistro: async () => registro,
      // O formulário já está na v2, mas o registro nasceu na v1 (versao_id 51).
      obterFormulario: async () => formulario(2, DEFINICAO_V2),
      obterVersao: async () => ({
        id: 51,
        formulario_id: 5,
        numero: 1,
        definicao: DEFINICAO_V1,
        publicada_em: "x",
      }),
      previa,
      ...extra,
    });
  }

  it("usa a definição da versão do registro, não a atual", async () => {
    const obterVersao = vi.fn(async () => ({
      id: 51,
      formulario_id: 5,
      numero: 1,
      definicao: DEFINICAO_V1,
      publicada_em: "x",
    }));
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "editar", registroId: 9 }} navegar={vi.fn()} />,
      clienteDeEdicao({ obterVersao }),
    );

    expect(await screen.findByLabelText(/fck/)).toHaveValue("25");
    expect(screen.queryByLabelText("Lote")).not.toBeInTheDocument(); // campo da v2, não da v1
    expect(screen.getByText("Versão 1 do formulário")).toBeInTheDocument();
    expect(obterVersao).toHaveBeenCalledWith(5, 51);
  });

  it("mostra o calculado já gravado e salva com PUT, substituindo os valores", async () => {
    const atualizarRegistro = vi.fn(async () => registro);
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "editar", registroId: 9 }} navegar={navegar} />,
      clienteDeEdicao({ atualizarRegistro }),
    );

    expect(await screen.findByLabelText(/Dobro/)).toHaveTextContent("50");
    await userEvent.clear(screen.getByLabelText(/fck/));
    await userEvent.type(screen.getByLabelText(/fck/), "30");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(navegar).toHaveBeenCalled());
    expect(atualizarRegistro).toHaveBeenCalledWith(9, { fck: "30" });
  });

  it("exclui só depois da confirmação", async () => {
    const excluirRegistro = vi.fn(async () => undefined);
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "editar", registroId: 9 }} navegar={navegar} />,
      clienteDeEdicao({ excluirRegistro }),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Excluir registro" }));
    expect(excluirRegistro).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    await waitFor(() =>
      expect(navegar).toHaveBeenCalledWith({ nome: "registros", formularioId: 5 }),
    );
    expect(excluirRegistro).toHaveBeenCalledWith(9);
  });

  it("mostra a mensagem do 409 quando outro registro referencia este", async () => {
    const excluirRegistro = vi.fn(async () => {
      throw new ErroDaApi(
        409,
        "O registro 9 é referenciado pelos registros 12 e não pode ser excluído.",
      );
    });
    const navegar = vi.fn();
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "editar", registroId: 9 }} navegar={navegar} />,
      clienteDeEdicao({ excluirRegistro }),
    );

    await userEvent.click(await screen.findByRole("button", { name: "Excluir registro" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("referenciado pelos registros 12");
    expect(navegar).not.toHaveBeenCalled();
  });

  it("novo registro não oferece exclusão", async () => {
    renderizarComApi(
      <PaginaDeRegistro modo={{ tipo: "novo", formularioId: 5 }} navegar={vi.fn()} />,
      clienteFalso({ obterFormulario: async () => formulario(2, DEFINICAO_V2), previa }),
    );

    await screen.findByRole("button", { name: "Salvar" });

    expect(screen.queryByRole("button", { name: "Excluir registro" })).not.toBeInTheDocument();
  });
});
