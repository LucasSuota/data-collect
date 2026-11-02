import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi, type Esquemas } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { Construtor, type ModoDoConstrutor } from "./Construtor";

type Catalogo = Esquemas["CatalogoSaida"];

const COMUNS = ["id", "tipo", "rotulo"];
const CATALOGO: Catalogo = {
  tipos: [
    { id: "texto", rotulo: "Texto", propriedades: [...COMUNS, "obrigatorio", "compartilhado"] },
    {
      id: "numero",
      rotulo: "Número",
      propriedades: [...COMUNS, "obrigatorio", "unidade", "casas_decimais", "compartilhado"],
    },
    {
      id: "selecao",
      rotulo: "Seleção",
      propriedades: [...COMUNS, "obrigatorio", "opcoes", "compartilhado"],
    },
    {
      id: "calculado",
      rotulo: "Calculado",
      propriedades: [...COMUNS, "formula", "unidade", "casas_decimais", "compartilhado"],
    },
    {
      id: "referencia",
      rotulo: "Referência",
      propriedades: [...COMUNS, "obrigatorio", "formulario"],
    },
    {
      id: "foto",
      rotulo: "Foto",
      propriedades: [...COMUNS, "obrigatorio", "maximo", "compartilhado"],
    },
    { id: "secao", rotulo: "Seção", propriedades: [...COMUNS] },
  ],
  funcoes: [
    { nome: "soma", assinatura: "soma(a, b, ...)", descricao: "Soma.", exemplo: "soma(a, b)" },
  ],
  constantes: [{ nome: "pi", valor: "3.14", tipo: "numero", descricao: "π" }],
  nomes_reservados: ["pi", "soma"],
};

const resumos = [
  { id: 1, nome: "Ensaio", criado_em: "x", versao_atual_id: 1, versao_atual_numero: 1 },
  { id: 2, nome: "Proctor", criado_em: "x", versao_atual_id: 2, versao_atual_numero: 1 },
];

const valida = async () => ({ valida: true, erros: [] });

function renderizar(modo: ModoDoConstrutor = { tipo: "novo" }, extra = {}) {
  const navegar = vi.fn();
  const cliente = clienteFalso({
    catalogo: async () => CATALOGO,
    listarFormularios: async () => resumos,
    validarDefinicao: valida,
    ...extra,
  });
  renderizarComApi(<Construtor modo={modo} navegar={navegar} atrasoDaValidacaoMs={10} />, cliente);
  return { navegar, cliente };
}

async function adicionar(rotulo: string) {
  await userEvent.click(await screen.findByRole("button", { name: `Adicionar campo ${rotulo}` }));
}

function nomesDosCampos(): string[] {
  const lista = screen.getByRole("region", { name: "Campos do formulário" });
  return within(lista)
    .getAllByRole("button", { name: /^Selecionar o campo/ })
    .map((b) => b.getAttribute("aria-label")?.replace("Selecionar o campo ", "") ?? "");
}

describe("Construtor: montagem da definição", () => {
  it("a paleta vem do catálogo", async () => {
    renderizar();

    const paleta = await screen.findByRole("region", { name: "Tipos de campo" });

    // A alça de arrasto do dnd-kit também tem role="button"; a paleta são os botões de adicionar.
    const botoes = within(paleta).getAllByRole("button", { name: /^Adicionar campo/ });
    expect(botoes.map((b) => b.textContent)).toEqual([
      "Texto",
      "Número",
      "Seleção",
      "Calculado",
      "Referência",
      "Foto",
      "Seção",
    ]);
  });

  it("adicionar cria o campo e o seleciona para edição", async () => {
    renderizar();
    await adicionar("Número");

    expect(nomesDosCampos()).toEqual(["Número"]);
    expect(screen.getByLabelText("Identificador (id)")).toHaveValue("numero_1");
    expect(screen.getByRole("button", { name: "Selecionar o campo Número" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("remove um campo e limpa o painel se ele estava selecionado", async () => {
    renderizar();
    await adicionar("Texto");
    await adicionar("Número");

    await userEvent.click(screen.getByRole("button", { name: "Remover o campo Número" }));

    expect(nomesDosCampos()).toEqual(["Texto"]);
    expect(screen.getByText(/Selecione um campo/)).toBeInTheDocument();
  });

  it("reordena para cima e para baixo, e os botões dos extremos ficam desabilitados", async () => {
    renderizar();
    await adicionar("Texto");
    await adicionar("Número");
    await adicionar("Foto");

    await userEvent.click(screen.getByRole("button", { name: "Mover Foto para cima" }));
    expect(nomesDosCampos()).toEqual(["Texto", "Foto", "Número"]);
    await userEvent.click(screen.getByRole("button", { name: "Mover Texto para baixo" }));
    expect(nomesDosCampos()).toEqual(["Foto", "Texto", "Número"]);

    expect(screen.getByRole("button", { name: "Mover Foto para cima" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mover Número para baixo" })).toBeDisabled();
  });

  it("a ordem na tela é a ordem da definição enviada ao servidor", async () => {
    const criarFormulario = vi.fn<
      (entrada: { nome: string; definicao: unknown }) => Promise<never>
    >(() => Promise.resolve({} as never));
    renderizar({ tipo: "novo" }, { criarFormulario });
    await userEvent.type(await screen.findByLabelText("Nome do formulário"), "Obra");
    await adicionar("Texto");
    await adicionar("Número");
    await userEvent.click(screen.getByRole("button", { name: "Mover Número para cima" }));

    await userEvent.click(screen.getByRole("button", { name: "Publicar formulário" }));

    const definicao = criarFormulario.mock.calls[0]?.[0]?.definicao as { campos: { id: string }[] };
    expect(definicao.campos.map((c) => c.id)).toEqual(["numero_1", "texto_1"]);
  });
});

describe("Construtor: painel de propriedades guiado pelo catálogo", () => {
  it("mostra só as propriedades que o tipo aceita", async () => {
    renderizar();
    await adicionar("Texto");

    expect(screen.getByLabelText("Obrigatório")).toBeInTheDocument();
    expect(screen.queryByLabelText("Unidade")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Casas decimais")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Opções/)).not.toBeInTheDocument();
  });

  it("número tem unidade e casas decimais; seleção tem opções; foto tem máximo", async () => {
    renderizar();
    await adicionar("Número");
    expect(screen.getByLabelText("Unidade")).toBeInTheDocument();
    expect(screen.getByLabelText("Casas decimais")).toBeInTheDocument();

    await adicionar("Seleção");
    expect(screen.getByLabelText(/Opções/)).toBeInTheDocument();

    await adicionar("Foto");
    expect(screen.getByLabelText("Máximo de fotos")).toBeInTheDocument();
  });

  it("trocar o tipo troca as propriedades oferecidas", async () => {
    renderizar();
    await adicionar("Número");

    await userEvent.selectOptions(screen.getByLabelText("Tipo"), "Texto");

    expect(screen.queryByLabelText("Unidade")).not.toBeInTheDocument();
  });

  it("referência escolhe o formulário de origem entre os existentes", async () => {
    renderizar();
    await adicionar("Referência");

    const select = screen.getByLabelText("Formulário de origem");

    expect(
      within(select)
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["— escolha —", "Ensaio", "Proctor"]);
  });

  it("ao editar um formulário, ele mesmo não é oferecido como origem", async () => {
    const formulario = {
      id: 2,
      nome: "Proctor",
      criado_em: "x",
      versao_atual: {
        id: 2,
        formulario_id: 2,
        numero: 1,
        definicao: {
          campos: [{ id: "e", tipo: "referencia" as const, rotulo: "E", formulario: "Ensaio" }],
        },
        publicada_em: "x",
      },
    };
    renderizar({ tipo: "editar", formularioId: 2 }, { obterFormulario: async () => formulario });
    await userEvent.click(await screen.findByRole("button", { name: "Selecionar o campo E" }));

    const opcoes = within(screen.getByLabelText("Formulário de origem"))
      .getAllByRole("option")
      .map((o) => o.textContent);

    expect(opcoes).toEqual(["— escolha —", "Ensaio"]);
  });

  it("o campo calculado usa o editor de fórmulas com os campos referenciáveis e o catálogo", async () => {
    renderizar();
    await adicionar("Número");
    await adicionar("Texto");
    await adicionar("Calculado");

    const campos = screen.getByRole("group", { name: "Campos e constantes" });

    expect(within(campos).getByRole("button", { name: "numero_1" })).toBeInTheDocument();
    expect(within(campos).queryByRole("button", { name: "texto_1" })).not.toBeInTheDocument(); // texto não entra em fórmula
    expect(within(campos).queryByRole("button", { name: "calculado_1" })).not.toBeInTheDocument(); // nem ele mesmo
    expect(within(campos).getByRole("button", { name: "pi" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Funções disponíveis" })).toHaveTextContent(
      "soma(a, b, ...)",
    );
  });

  it("edita rótulo e id e a lista acompanha", async () => {
    renderizar();
    await adicionar("Texto");

    await userEvent.clear(screen.getByLabelText("Rótulo"));
    await userEvent.type(screen.getByLabelText("Rótulo"), "Observação");

    expect(nomesDosCampos()).toEqual(["Observação"]);
  });
});

describe("Construtor: validação e erros no campo certo", () => {
  it("valida no servidor com debounce, mandando a definição montada", async () => {
    const validarDefinicao = vi.fn(valida);
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Número");
    await userEvent.type(screen.getByLabelText("Unidade"), "MPa");

    // Espera pela própria afirmação: a primeira chamada pode sair antes de acabar de digitar.
    await waitFor(() =>
      expect(validarDefinicao).toHaveBeenLastCalledWith({
        campos: [{ id: "numero_1", tipo: "numero", rotulo: "Número", unidade: "MPa" }],
      }),
    );
  });

  it("não envia propriedade que o tipo atual não aceita", async () => {
    const validarDefinicao = vi.fn(valida);
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Número");
    await userEvent.type(screen.getByLabelText("Unidade"), "kg");
    await userEvent.selectOptions(screen.getByLabelText("Tipo"), "Texto");

    await waitFor(() =>
      expect(validarDefinicao).toHaveBeenLastCalledWith({
        campos: [{ id: "numero_1", tipo: "texto", rotulo: "Número" }],
      }),
    );
  });

  it("mostra cada erro do servidor na propriedade do campo certo", async () => {
    const validarDefinicao = vi.fn(async () => ({
      valida: false,
      erros: [
        {
          campo: "numero_1.casas_decimais",
          mensagem: "As casas decimais devem ser um inteiro a partir de 0.",
        },
        { campo: "texto_1.rotulo", mensagem: "O rótulo é obrigatório e não pode ficar vazio." },
      ],
    }));
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Número");
    await adicionar("Texto");

    expect(await screen.findByText("2 erro(s)", { exact: false }).catch(() => null)).toBeNull();
    await waitFor(() => expect(screen.getAllByText("1 erro(s)")).toHaveLength(2));
    await userEvent.click(screen.getByRole("button", { name: "Selecionar o campo Número" }));

    expect(screen.getByLabelText("Casas decimais")).toHaveAccessibleDescription(
      /inteiro a partir de 0/,
    );
  });

  it("reordenar os campos não desloca os erros: eles seguem o campo", async () => {
    const validarDefinicao = vi.fn(async () => ({
      valida: false,
      erros: [{ campo: "campos[1].id", mensagem: "O id 'x' é reservado." }],
    }));
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Texto");
    await adicionar("Número"); // posição 1: é ele que tem o erro
    await waitFor(() => expect(validarDefinicao).toHaveBeenCalledTimes(1));
    await screen.findByText("1 erro(s)");

    // Move o campo com erro para o topo, ANTES de uma nova validação responder.
    await userEvent.click(screen.getByRole("button", { name: "Mover Número para cima" }));

    const itens = within(screen.getByRole("region", { name: "Campos do formulário" })).getAllByRole(
      "listitem",
    );
    expect(within(itens[0] as HTMLElement).getByText("Número")).toBeInTheDocument();
    expect(within(itens[0] as HTMLElement).getByText("1 erro(s)")).toBeInTheDocument();
    expect(within(itens[1] as HTMLElement).queryByText("1 erro(s)")).not.toBeInTheDocument();
  });

  it("o erro de fórmula chega ao editor com a posição para sublinhar", async () => {
    const validarDefinicao = vi.fn(async () => ({
      valida: false,
      erros: [
        {
          campo: "calculado_1.formula",
          mensagem: "Função 'raiz' não permitida.",
          posicao: { inicio: 4, fim: 11 },
        },
      ],
    }));
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Calculado");
    await userEvent.type(screen.getByLabelText("Fórmula"), "1 + raiz(4)");

    expect(await screen.findByTestId("trecho-com-erro")).toHaveTextContent("raiz(4)");
    expect(screen.getByRole("alert")).toHaveTextContent("Função 'raiz' não permitida.");
  });

  it("erro global (definição sem campos) aparece no topo", async () => {
    const validarDefinicao = vi.fn(async () => ({
      valida: false,
      erros: [{ campo: "campos", mensagem: "A definição precisa ter a lista 'campos'." }],
    }));
    renderizar({ tipo: "novo" }, { validarDefinicao });
    await adicionar("Texto");

    expect(await screen.findByText(/A definição precisa ter a lista/)).toBeInTheDocument();
  });

  it("uma validação que falha por falta de conexão não derruba a tela", async () => {
    const validarDefinicao = vi.fn(async () => {
      throw new ErroDaApi(0, "Não foi possível conectar à API.");
    });
    renderizar({ tipo: "novo" }, { validarDefinicao });

    await adicionar("Texto");

    await waitFor(() => expect(validarDefinicao).toHaveBeenCalled());
    expect(nomesDosCampos()).toEqual(["Texto"]);
  });
});

describe("Construtor: publicar", () => {
  it("novo formulário: cria com o nome e a definição e volta à lista", async () => {
    const criarFormulario = vi.fn<
      (entrada: { nome: string; definicao: unknown }) => Promise<never>
    >(() => Promise.resolve({} as never));
    const { navegar } = renderizar({ tipo: "novo" }, { criarFormulario });
    await userEvent.type(await screen.findByLabelText("Nome do formulário"), "Corpo de prova");
    await adicionar("Número");
    await userEvent.type(screen.getByLabelText("Unidade"), "MPa");

    await userEvent.click(screen.getByRole("button", { name: "Publicar formulário" }));

    await waitFor(() => expect(navegar).toHaveBeenCalledWith({ nome: "formularios" }));
    expect(criarFormulario).toHaveBeenCalledWith({
      nome: "Corpo de prova",
      definicao: { campos: [{ id: "numero_1", tipo: "numero", rotulo: "Número", unidade: "MPa" }] },
    });
  });

  it("422 mostra os erros nos campos e o do nome junto ao nome, sem navegar", async () => {
    const criarFormulario = vi.fn(async () => {
      throw new ErroDaApi(422, "Definição inválida.", [
        { campo: "nome", mensagem: "Já existe um formulário com este nome." },
        { campo: "texto_1.rotulo", mensagem: "O rótulo é obrigatório." },
      ]);
    });
    const { navegar } = renderizar({ tipo: "novo" }, { criarFormulario });
    await userEvent.type(await screen.findByLabelText("Nome do formulário"), "Repetido");
    await adicionar("Texto");

    await userEvent.click(screen.getByRole("button", { name: "Publicar formulário" }));

    expect(await screen.findByText("Já existe um formulário com este nome.")).toBeInTheDocument();
    expect(screen.getByLabelText("Rótulo")).toHaveAccessibleDescription("O rótulo é obrigatório.");
    expect(navegar).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Publicar formulário" })).toBeEnabled();
  });

  it("falha de conexão ao publicar mostra o aviso e mantém o trabalho", async () => {
    const criarFormulario = vi.fn(async () => {
      throw new ErroDaApi(0, "Não foi possível conectar à API.");
    });
    renderizar({ tipo: "novo" }, { criarFormulario });
    await adicionar("Texto");

    await userEvent.click(screen.getByRole("button", { name: "Publicar formulário" }));

    expect(await screen.findByText("Não foi possível conectar à API.")).toBeInTheDocument();
    expect(nomesDosCampos()).toEqual(["Texto"]);
  });

  it("não publica duas vezes enquanto publica", async () => {
    let concluir: () => void = () => {};
    const criarFormulario = vi.fn(
      () => new Promise<never>((resolve) => (concluir = () => resolve({} as never))),
    );
    renderizar({ tipo: "novo" }, { criarFormulario });
    await adicionar("Texto");

    await userEvent.click(screen.getByRole("button", { name: "Publicar formulário" }));

    expect(screen.getByRole("button", { name: "Publicando…" })).toBeDisabled();
    await act(async () => concluir());
  });
});

describe("Construtor: editar um formulário (nova versão)", () => {
  const formulario = {
    id: 5,
    nome: "Corpo de prova",
    criado_em: "x",
    versao_atual: {
      id: 51,
      formulario_id: 5,
      numero: 2,
      publicada_em: "x",
      definicao: {
        campos: [
          { id: "fck", tipo: "numero" as const, rotulo: "fck", unidade: "MPa", obrigatorio: true },
          {
            id: "dobro",
            tipo: "calculado" as const,
            rotulo: "Dobro",
            formula: "fck * 2",
            casas_decimais: 1,
          },
        ],
      },
    },
  };

  it("carrega a versão atual e avisa que publicar cria a próxima", async () => {
    renderizar({ tipo: "editar", formularioId: 5 }, { obterFormulario: async () => formulario });

    expect(
      await screen.findByRole("heading", { name: "Editar · Corpo de prova" }),
    ).toBeInTheDocument();
    expect(nomesDosCampos()).toEqual(["fck", "Dobro"]);
    expect(screen.getByText(/cria a versão 3/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Nome do formulário")).not.toBeInTheDocument();
  });

  it("publica a nova versão com a definição editada", async () => {
    const publicarVersao = vi.fn<(id: number, definicao: unknown) => Promise<never>>(
      async () => ({}) as never,
    );
    const { navegar } = renderizar(
      { tipo: "editar", formularioId: 5 },
      { obterFormulario: async () => formulario, publicarVersao },
    );
    await adicionar("Texto");

    await userEvent.click(screen.getByRole("button", { name: "Publicar nova versão" }));

    await waitFor(() => expect(navegar).toHaveBeenCalledWith({ nome: "formularios" }));
    const [id, definicao] = publicarVersao.mock.calls[0] ?? [];
    expect(id).toBe(5);
    expect((definicao as { campos: { id: string }[] }).campos.map((c) => c.id)).toEqual([
      "fck",
      "dobro",
      "texto_1",
    ]);
  });

  it("422 do contrato entre versões aparece no campo que o servidor citou", async () => {
    const publicarVersao = vi.fn(async () => {
      throw new ErroDaApi(422, "Definição inválida.", [
        {
          campo: "fck.tipo",
          mensagem: "O campo 'fck' é usado por 'Proctor' e não pode mudar de tipo.",
        },
      ]);
    });
    renderizar(
      { tipo: "editar", formularioId: 5 },
      { obterFormulario: async () => formulario, publicarVersao },
    );
    await userEvent.click(await screen.findByRole("button", { name: "Publicar nova versão" }));

    await userEvent.click(await screen.findByRole("button", { name: "Selecionar o campo fck" }));

    expect(await screen.findByText(/é usado por 'Proctor'/)).toBeInTheDocument();
  });

  it("formulário inexistente mostra o erro do servidor", async () => {
    renderizar(
      { tipo: "editar", formularioId: 99 },
      {
        obterFormulario: async () => {
          throw new ErroDaApi(404, "Formulário 99 não encontrado.");
        },
      },
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Formulário 99 não encontrado.");
  });
});
