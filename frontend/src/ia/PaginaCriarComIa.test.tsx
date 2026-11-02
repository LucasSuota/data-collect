import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi, type ClienteApi, type Esquemas } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaCriarComIa } from "./PaginaCriarComIa";

type Gerado = Esquemas["RascunhoGeradoSaida"];

const CATALOGO: Esquemas["CatalogoSaida"] = {
  tipos: [
    { id: "texto", rotulo: "Texto", propriedades: ["id", "tipo", "rotulo", "obrigatorio"] },
    { id: "numero", rotulo: "Número", propriedades: ["id", "tipo", "rotulo", "unidade"] },
  ],
  funcoes: [],
  constantes: [],
  nomes_reservados: [],
};

const ENSAIO: Gerado = {
  nome: "Ensaio",
  definicao: { campos: [{ id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%" }] },
  erros: [],
};
const PROCTOR: Gerado = {
  nome: "Proctor",
  definicao: { campos: [{ id: "x", tipo: "numero", rotulo: "X" }] },
  erros: [
    { campo: "x.formula", mensagem: "Campo desconhecido 'y'." },
    { campo: "nome", mensagem: "Nome repetido." },
  ],
};

function renderizar(extra: Partial<ClienteApi> = {}) {
  const navegar = vi.fn();
  const cliente = clienteFalso({
    catalogo: async () => CATALOGO,
    listarFormularios: async () => [],
    ...extra,
  });
  renderizarComApi(<PaginaCriarComIa navegar={navegar} />, cliente);
  return { navegar, cliente };
}

async function gerar(pedido = "ensaio e proctor") {
  await userEvent.type(screen.getByLabelText("O que você quer criar?"), pedido);
  await userEvent.click(screen.getByRole("button", { name: "Gerar formulários" }));
}

function cartao(nome: string) {
  const lista = screen.getByRole("region", { name: "Rascunhos" });
  const campo = within(lista)
    .getAllByRole("textbox")
    .find((entrada) => (entrada as HTMLInputElement).value === nome);
  if (!campo) throw new Error(`Sem rascunho chamado ${nome}`);
  return within(campo.closest("li") as HTMLElement);
}

describe("PaginaCriarComIa: gerar", () => {
  it("só gera quando há pedido", async () => {
    renderizar();

    expect(screen.getByRole("button", { name: "Gerar formulários" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("O que você quer criar?"), "   ");
    expect(screen.getByRole("button", { name: "Gerar formulários" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("O que você quer criar?"), "um ensaio");
    expect(screen.getByRole("button", { name: "Gerar formulários" })).toBeEnabled();
  });

  it("limita o pedido ao tamanho que o servidor aceita", () => {
    renderizar();

    expect(screen.getByLabelText("O que você quer criar?")).toHaveAttribute("maxlength", "4000");
  });

  it("envia o pedido e mostra cada formulário proposto com a situação dos erros", async () => {
    const gerarFormularios = vi.fn(async () => ({ formularios: [ENSAIO, PROCTOR] }));
    renderizar({ gerarFormularios });

    await gerar("ensaio e proctor");

    expect(gerarFormularios).toHaveBeenCalledWith({ pedido: "ensaio e proctor", rascunhos: [] });
    expect(await screen.findByDisplayValue("Ensaio")).toBeInTheDocument();
    expect(cartao("Ensaio").getByText("Sem erros")).toBeInTheDocument();
    expect(cartao("Proctor").getByText("2 erro(s)")).toBeInTheDocument();
    expect(cartao("Proctor").getByText("x.formula: Campo desconhecido 'y'.")).toBeInTheDocument();
  });

  it("enquanto a IA responde, o botão avisa e não deixa gerar de novo", async () => {
    let concluir: (valor: { formularios: Gerado[] }) => void = () => undefined;
    const gerarFormularios = vi.fn(
      () => new Promise<{ formularios: Gerado[] }>((resolver) => (concluir = resolver)),
    );
    renderizar({ gerarFormularios });

    await gerar();

    const botao = screen.getByRole("button", { name: "Gerando…" });
    expect(botao).toBeDisabled();
    concluir({ formularios: [ENSAIO] });
    expect(await screen.findByDisplayValue("Ensaio")).toBeInTheDocument();
    expect(gerarFormularios).toHaveBeenCalledOnce();
  });

  it("IA indisponível (503) explica e aponta o construtor manual", async () => {
    renderizar({
      gerarFormularios: async () => {
        throw new ErroDaApi(503, "A IA está indisponível: defina ANTHROPIC_API_KEY no .env.");
      },
    });

    await gerar();

    expect(await screen.findByRole("alert")).toHaveTextContent("A IA está indisponível");
    expect(screen.getByRole("link", { name: "Usar o construtor manual" })).toHaveAttribute(
      "href",
      "#/construtor",
    );
    expect(screen.queryByRole("region", { name: "Rascunhos" })).not.toBeInTheDocument();
  });

  it("outro erro da API aparece como alerta e o pedido é mantido para tentar de novo", async () => {
    renderizar({
      gerarFormularios: async () => {
        throw new ErroDaApi(502, "A IA respondeu fora do formato esperado.");
      },
    });

    await gerar("meu pedido");

    expect(await screen.findByRole("alert")).toHaveTextContent("fora do formato");
    expect(screen.getByLabelText("O que você quer criar?")).toHaveValue("meu pedido");
    expect(screen.getByRole("button", { name: "Gerar formulários" })).toBeEnabled();
  });
});

describe("PaginaCriarComIa: ajustar os rascunhos", () => {
  async function comRascunhos(extra: Partial<ClienteApi> = {}) {
    const gerarFormularios = vi.fn(async () => ({ formularios: [ENSAIO, PROCTOR] }));
    const resto = renderizar({ gerarFormularios, ...extra });
    await gerar();
    await screen.findByDisplayValue("Ensaio");
    return { ...resto, gerarFormularios };
  }

  it("remove um rascunho", async () => {
    await comRascunhos();

    await userEvent.click(screen.getByRole("button", { name: "Remover o rascunho Proctor" }));

    expect(screen.queryByDisplayValue("Proctor")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Ensaio")).toBeInTheDocument();
  });

  it("refinar manda o novo pedido junto com os rascunhos como estão (nome editado inclusive)", async () => {
    const { gerarFormularios } = await comRascunhos();
    const nome = screen.getByDisplayValue("Ensaio");
    await userEvent.clear(nome);
    await userEvent.type(nome, "Ensaio de umidade");
    const pedido = screen.getByLabelText("O que você quer criar?");
    await userEvent.clear(pedido);
    await userEvent.type(pedido, "adicione o campo massa");
    gerarFormularios.mockResolvedValueOnce({ formularios: [ENSAIO] });

    await userEvent.click(screen.getByRole("button", { name: "Refinar rascunhos" }));

    await waitFor(() => expect(gerarFormularios).toHaveBeenCalledTimes(2));
    expect(gerarFormularios).toHaveBeenLastCalledWith({
      pedido: "adicione o campo massa",
      rascunhos: [
        { nome: "Ensaio de umidade", definicao: ENSAIO.definicao },
        { nome: "Proctor", definicao: PROCTOR.definicao },
      ],
    });
    // a resposta substitui os rascunhos
    expect(await screen.findByDisplayValue("Ensaio")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Proctor")).not.toBeInTheDocument();
  });

  it("edita um rascunho no construtor e volta com a definição alterada", async () => {
    const criarFormulariosEmLote = vi.fn(async () => []);
    await comRascunhos({ criarFormulariosEmLote });

    await userEvent.click(screen.getByRole("button", { name: "Editar o rascunho Ensaio" }));
    await userEvent.click(await screen.findByRole("button", { name: "Adicionar campo Texto" }));
    await userEvent.click(screen.getByRole("button", { name: "Concluir edição" }));
    await userEvent.click(await screen.findByRole("button", { name: "Publicar todos" }));

    expect(criarFormulariosEmLote).toHaveBeenCalledWith([
      {
        nome: "Ensaio",
        definicao: {
          campos: [
            { id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%" },
            { id: "texto_1", tipo: "texto", rotulo: "Texto" },
          ],
        },
      },
      { nome: "Proctor", definicao: PROCTOR.definicao },
    ]);
  });

  it("cancelar a edição mantém o rascunho como estava", async () => {
    const criarFormulariosEmLote = vi.fn(async () => []);
    await comRascunhos({ criarFormulariosEmLote });

    await userEvent.click(screen.getByRole("button", { name: "Editar o rascunho Ensaio" }));
    await userEvent.click(await screen.findByRole("button", { name: "Adicionar campo Texto" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    await userEvent.click(await screen.findByRole("button", { name: "Publicar todos" }));

    expect(criarFormulariosEmLote).toHaveBeenCalledWith([
      { nome: "Ensaio", definicao: ENSAIO.definicao },
      { nome: "Proctor", definicao: PROCTOR.definicao },
    ]);
  });
});

describe("PaginaCriarComIa: publicar todos", () => {
  async function comRascunhos(extra: Partial<ClienteApi> = {}) {
    const resto = renderizar({
      gerarFormularios: async () => ({ formularios: [ENSAIO, PROCTOR] }),
      ...extra,
    });
    await gerar();
    await screen.findByDisplayValue("Ensaio");
    return resto;
  }

  it("não há o que publicar sem rascunhos", () => {
    renderizar();

    expect(screen.queryByRole("button", { name: "Publicar todos" })).not.toBeInTheDocument();
  });

  it("publica o conjunto de uma vez e volta para a lista", async () => {
    const criarFormulariosEmLote = vi.fn(async () => []);
    const { navegar } = await comRascunhos({ criarFormulariosEmLote });

    await userEvent.click(screen.getByRole("button", { name: "Publicar todos" }));

    expect(criarFormulariosEmLote).toHaveBeenCalledOnce();
    expect(criarFormulariosEmLote).toHaveBeenCalledWith([
      { nome: "Ensaio", definicao: ENSAIO.definicao },
      { nome: "Proctor", definicao: PROCTOR.definicao },
    ]);
    await waitFor(() => expect(navegar).toHaveBeenCalledWith({ nome: "formularios" }));
  });

  it("422: nada foi criado, e cada erro volta para o rascunho certo", async () => {
    const criarFormulariosEmLote = vi.fn(async () => {
      throw new ErroDaApi(422, "Há formulários inválidos no lote; nada foi criado.", [
        { campo: "Proctor.umidade.formula", mensagem: "Campo desconhecido." },
        { campo: "Ensaio.nome", mensagem: "Já existe um formulário com este nome." },
      ]);
    });
    const { navegar } = await comRascunhos({ criarFormulariosEmLote });

    await userEvent.click(screen.getByRole("button", { name: "Publicar todos" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("nada foi criado");
    expect(cartao("Proctor").getByText("1 erro(s)")).toBeInTheDocument();
    expect(cartao("Proctor").getByText("umidade.formula: Campo desconhecido.")).toBeInTheDocument();
    expect(
      cartao("Ensaio").getByText("nome: Já existe um formulário com este nome."),
    ).toBeInTheDocument();
    expect(navegar).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Publicar todos" })).toBeEnabled();
  });

  it("falha de conexão ao publicar mostra o motivo e mantém os rascunhos", async () => {
    const criarFormulariosEmLote = vi.fn(async () => {
      throw new ErroDaApi(0, "Não foi possível conectar à API.");
    });
    const { navegar } = await comRascunhos({ criarFormulariosEmLote });

    await userEvent.click(screen.getByRole("button", { name: "Publicar todos" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível conectar");
    expect(screen.getByDisplayValue("Ensaio")).toBeInTheDocument();
    expect(navegar).not.toHaveBeenCalled();
  });
});
