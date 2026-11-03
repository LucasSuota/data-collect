import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi, type ClienteApi } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaDeFormularios } from "./PaginaDeFormularios";
import type { Pasta } from "./pastas";

const pasta = (id: number, nome: string, pasta_pai_id: number | null = null): Pasta => ({
  id,
  nome,
  pasta_pai_id,
  criado_em: "2026-11-02T10:00:00+00:00",
});

const resumo = (id: number, nome: string, pasta_id: number | null = null) => ({
  id,
  nome,
  criado_em: "2026-11-02T10:00:00+00:00",
  versao_atual_id: id * 10,
  versao_atual_numero: 1,
  pasta_id,
});

const OBRAS = pasta(1, "Obras");
const LAB = pasta(2, "Laboratório");
const FUNDACAO = pasta(3, "Fundação", 1);

const FORMULARIOS = [
  resumo(10, "Sem pasta"),
  resumo(11, "Sondagem", 1),
  resumo(12, "Estacas SPT", 3),
];

function renderizar(pastaId: number | null, extra: Partial<ClienteApi> = {}) {
  const navegar = vi.fn();
  renderizarComApi(
    <PaginaDeFormularios navegar={navegar} pastaId={pastaId} />,
    clienteFalso({
      listarFormularios: async () => FORMULARIOS,
      listarPastas: async () => [OBRAS, LAB, FUNDACAO],
      ...extra,
    }),
  );
  return { navegar };
}

describe("PaginaDeFormularios: navegação pelas pastas", () => {
  it("na raiz mostra as pastas de cima e só os formulários sem pasta", async () => {
    renderizar(null);

    expect(await screen.findByText("Sem pasta")).toBeInTheDocument();
    expect(screen.queryByText("Sondagem")).not.toBeInTheDocument();
    const subpastas = screen.getByRole("list", { name: "Pastas desta pasta" });
    expect(within(subpastas).getByText("Obras")).toBeInTheDocument();
    expect(within(subpastas).getByText("Laboratório")).toBeInTheDocument();
    expect(within(subpastas).queryByText("Fundação")).not.toBeInTheDocument();
  });

  it("dentro de uma pasta mostra o caminho, as subpastas e os formulários dela", async () => {
    renderizar(1);

    expect(await screen.findByText("Sondagem")).toBeInTheDocument();
    expect(screen.queryByText("Sem pasta")).not.toBeInTheDocument();
    expect(screen.queryByText("Estacas SPT")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Obras" })).toBeInTheDocument();
    const subpastas = screen.getByRole("list", { name: "Pastas desta pasta" });
    expect(within(subpastas).getByText("Fundação")).toBeInTheDocument();
  });

  it("a trilha de navegação leva de volta aos níveis de cima", async () => {
    const { navegar } = renderizar(3);
    await screen.findByText("Estacas SPT");
    const trilha = screen.getByRole("navigation", { name: "Caminho da pasta" });

    await userEvent.click(within(trilha).getByRole("link", { name: "Obras" }));
    await userEvent.click(within(trilha).getByRole("link", { name: "Formulários" }));

    expect(navegar.mock.calls.map(([rota]) => rota)).toEqual([
      { nome: "pasta", pastaId: 1 },
      { nome: "formularios" },
    ]);
  });

  it("abrir uma subpasta navega para ela", async () => {
    const { navegar } = renderizar(null);
    const subpastas = await screen.findByRole("list", { name: "Pastas desta pasta" });

    await userEvent.click(within(subpastas).getByRole("button", { name: /Obras/ }));

    expect(navegar).toHaveBeenCalledWith({ nome: "pasta", pastaId: 1 });
  });

  it("a árvore lateral mostra todas as pastas, com as filhas aninhadas", async () => {
    const { navegar } = renderizar(null);
    const arvore = await screen.findByRole("tree", { name: "Pastas" });

    expect(within(arvore).getByRole("treeitem", { name: /Obras/ })).toBeInTheDocument();
    expect(within(arvore).getByRole("treeitem", { name: /Fundação/ })).toBeInTheDocument();
    await userEvent.click(within(arvore).getByRole("button", { name: "Abrir a pasta Fundação" }));
    expect(navegar).toHaveBeenCalledWith({ nome: "pasta", pastaId: 3 });
  });

  it("pasta que não existe mostra um aviso com o caminho de volta", async () => {
    renderizar(99);

    expect(await screen.findByRole("alert")).toHaveTextContent("Pasta não encontrada");
    expect(screen.getByRole("link", { name: "Voltar aos formulários" })).toBeInTheDocument();
  });

  it("pasta vazia explica que está vazia e oferece criar um formulário", async () => {
    renderizar(2);

    expect(await screen.findByText("Esta pasta está vazia")).toBeInTheDocument();
  });

  it("Novo formulário cria dentro da pasta atual, e na raiz sem pasta", async () => {
    const { navegar } = renderizar(1);
    await userEvent.click(await screen.findByRole("button", { name: "Novo formulário" }));

    expect(navegar).toHaveBeenCalledWith({ nome: "novoFormulario", pastaId: 1 });
  });
});

describe("PaginaDeFormularios: criar, renomear, mover e excluir pastas", () => {
  it("cria uma pasta na raiz e recarrega a lista", async () => {
    const criarPasta = vi.fn(async () => pasta(5, "Nova"));
    const listarPastas = vi
      .fn()
      .mockResolvedValueOnce([OBRAS])
      .mockResolvedValueOnce([OBRAS, pasta(5, "Nova")]);
    renderizar(null, { criarPasta, listarPastas });

    await userEvent.click(await screen.findByRole("button", { name: "Nova pasta" }));
    await userEvent.type(screen.getByLabelText("Nome da pasta"), "  Nova  ");
    await userEvent.click(screen.getByRole("button", { name: "Criar pasta" }));

    expect(criarPasta).toHaveBeenCalledWith("Nova", null);
    const subpastas = await screen.findByRole("list", { name: "Pastas desta pasta" });
    expect(await within(subpastas).findByText("Nova")).toBeInTheDocument();
  });

  it("cria uma subpasta dentro da pasta atual", async () => {
    const criarPasta = vi.fn(async () => pasta(6, "Estacas", 1));
    renderizar(1, { criarPasta });

    await userEvent.click(await screen.findByRole("button", { name: "Nova pasta" }));
    await userEvent.type(screen.getByLabelText("Nome da pasta"), "Estacas");
    await userEvent.click(screen.getByRole("button", { name: "Criar pasta" }));

    expect(criarPasta).toHaveBeenCalledWith("Estacas", 1);
  });

  it("mostra o erro de nome repetido no campo e mantém o formulário aberto", async () => {
    const criarPasta = vi.fn(async () => {
      throw new ErroDaApi(422, "Pasta inválida.", [
        { campo: "nome", mensagem: "Já existe uma pasta com este nome neste local." },
      ]);
    });
    renderizar(null, { criarPasta });

    await userEvent.click(await screen.findByRole("button", { name: "Nova pasta" }));
    await userEvent.type(screen.getByLabelText("Nome da pasta"), "Obras");
    await userEvent.click(screen.getByRole("button", { name: "Criar pasta" }));

    expect(screen.getByLabelText("Nome da pasta")).toBeInTheDocument();
    expect(await screen.findByText("Já existe uma pasta com este nome neste local.")).toBeVisible();
    expect(screen.getByLabelText("Nome da pasta")).toHaveAttribute("aria-invalid", "true");
  });

  it("renomeia a pasta atual mantendo o lugar dela", async () => {
    const atualizarPasta = vi.fn(async () => pasta(3, "Estacas", 1));
    renderizar(3, { atualizarPasta });

    await userEvent.click(await screen.findByRole("button", { name: "Renomear a pasta" }));
    const campo = screen.getByLabelText("Novo nome");
    await userEvent.clear(campo);
    await userEvent.type(campo, "Estacas");
    await userEvent.click(screen.getByRole("button", { name: "Salvar nome" }));

    expect(atualizarPasta).toHaveBeenCalledWith(3, "Estacas", 1);
  });

  it("move a pasta atual para outra; a própria pasta e as filhas não são destinos", async () => {
    const atualizarPasta = vi.fn(async () => pasta(1, "Obras", 2));
    renderizar(1, { atualizarPasta });
    const seletor = await screen.findByLabelText("Mover a pasta para");

    const opcoes = within(seletor)
      .getAllByRole("option")
      .map((o) => o.textContent);
    await userEvent.selectOptions(seletor, "Laboratório");

    // Obras já está na raiz, então a raiz não é destino; a própria pasta e a filha também não.
    expect(opcoes).toEqual(["Mover para…", "Laboratório"]);
    expect(atualizarPasta).toHaveBeenCalledWith(1, "Obras", 2);
  });

  it("só exclui depois da confirmação e volta para a pasta de cima", async () => {
    const excluirPasta = vi.fn(async () => undefined);
    const { navegar } = renderizar(3, { excluirPasta });

    await userEvent.click(await screen.findByRole("button", { name: "Excluir a pasta" }));
    expect(excluirPasta).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão da pasta" }));

    expect(excluirPasta).toHaveBeenCalledWith(3);
    expect(navegar).toHaveBeenCalledWith({ nome: "pasta", pastaId: 1 });
  });

  it("explica o 409 quando a pasta não está vazia", async () => {
    const excluirPasta = vi.fn(async () => {
      throw new ErroDaApi(409, "A pasta 'Obras' tem 1 subpasta(s) e não pode ser excluída.");
    });
    renderizar(1, { excluirPasta });

    await userEvent.click(await screen.findByRole("button", { name: "Excluir a pasta" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirmar exclusão da pasta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("tem 1 subpasta(s)");
  });
});

describe("PaginaDeFormularios: mover formulários", () => {
  it("move o formulário para uma pasta pelo seletor", async () => {
    const moverFormulario = vi.fn(async () => resumo(10, "Sem pasta", 2));
    renderizar(null, { moverFormulario });
    const seletor = await screen.findByLabelText("Mover Sem pasta para");

    await userEvent.selectOptions(seletor, "Obras / Fundação");

    expect(moverFormulario).toHaveBeenCalledWith(10, 3);
  });

  it("devolve o formulário para a raiz", async () => {
    const moverFormulario = vi.fn(async () => resumo(11, "Sondagem"));
    renderizar(1, { moverFormulario });
    const seletor = await screen.findByLabelText("Mover Sondagem para");

    await userEvent.selectOptions(seletor, "Raiz (sem pasta)");

    expect(moverFormulario).toHaveBeenCalledWith(11, null);
  });

  it("não oferece a pasta onde o formulário já está", async () => {
    renderizar(1);
    const seletor = await screen.findByLabelText("Mover Sondagem para");

    const opcoes = within(seletor)
      .getAllByRole("option")
      .map((o) => o.textContent);

    expect(opcoes).not.toContain("Obras");
    expect(opcoes).toContain("Raiz (sem pasta)");
  });

  it("mostra a falha do servidor ao mover", async () => {
    const moverFormulario = vi.fn(async () => {
      throw new ErroDaApi(422, "Pasta inválida.", [
        { campo: "pasta_id", mensagem: "A pasta de destino não existe." },
      ]);
    });
    renderizar(null, { moverFormulario });

    await userEvent.selectOptions(await screen.findByLabelText("Mover Sem pasta para"), "Obras");

    expect(await screen.findByRole("alert")).toHaveTextContent("A pasta de destino não existe.");
  });
});

describe("PaginaDeFormularios: busca, escopo e ordem", () => {
  const buscar = async (texto: string) =>
    userEvent.type(screen.getByRole("searchbox", { name: "Buscar formulários e pastas" }), texto);

  it("a busca acha formulários de qualquer pasta e diz onde cada um está", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    await buscar("estacas");

    expect(screen.getByText("Estacas SPT")).toBeInTheDocument();
    expect(screen.getByText("Obras / Fundação")).toBeInTheDocument();
    expect(screen.queryByText("Sondagem")).not.toBeInTheDocument();
    expect(screen.getByText("Encontrado: 1 formulário e 0 pastas.")).toBeInTheDocument();
  });

  it("a busca também acha pastas, sem exigir acento", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    await buscar("fundacao");

    const pastas = screen.getByRole("list", { name: "Pastas encontradas" });
    expect(within(pastas).getByText("Fundação")).toBeInTheDocument();
    expect(within(pastas).getByText("em Obras")).toBeInTheDocument();
  });

  it("sem resultado, explica e oferece limpar a busca", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    await buscar("zzz");
    expect(screen.getByText("Nada encontrado")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Limpar a busca" }));
    expect(screen.getByText("Sem pasta")).toBeInTheDocument();
  });

  it("dentro de uma pasta, dá para limitar a busca a ela e às descendentes", async () => {
    renderizar(1);
    await screen.findByText("Sondagem");

    const arrastar = (nome: string) =>
      screen.queryByRole("button", { name: `Arrastar o formulário ${nome}` });

    await buscar("s");
    expect(arrastar("Sem pasta")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Onde buscar"), "pasta");
    expect(arrastar("Sem pasta")).not.toBeInTheDocument();
    expect(screen.getByText("Sondagem")).toBeInTheDocument();
    expect(screen.getByText("Estacas SPT")).toBeInTheDocument();
  });

  it("na raiz não há escolha de onde buscar", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    expect(screen.queryByLabelText("Onde buscar")).not.toBeInTheDocument();
  });

  it("abrir uma pasta pela busca limpa o termo", async () => {
    const { navegar } = renderizar(null);
    await screen.findByText("Sem pasta");
    await buscar("fund");

    await userEvent.click(
      within(screen.getByRole("list", { name: "Pastas encontradas" })).getByRole("button"),
    );

    expect(navegar).toHaveBeenCalledWith({ nome: "pasta", pastaId: 3 });
    expect(screen.getByRole("searchbox", { name: "Buscar formulários e pastas" })).toHaveValue("");
  });

  it("Esc limpa a busca", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");
    await buscar("sond{Escape}");

    expect(screen.getByRole("searchbox", { name: "Buscar formulários e pastas" })).toHaveValue("");
  });

  it("ordena a lista pelo seletor", async () => {
    renderizar(null, {
      listarFormularios: async () => [resumo(1, "Beta"), resumo(2, "Alfa"), resumo(3, "Gama")],
    });
    await screen.findByText("Alfa");
    const nomesNaTela = () =>
      screen
        .getAllByRole("button", { name: /^Arrastar o formulário / })
        .map((b) => b.getAttribute("aria-label")?.replace("Arrastar o formulário ", ""));
    expect(nomesNaTela()).toEqual(["Alfa", "Beta", "Gama"]);

    await userEvent.selectOptions(screen.getByLabelText("Ordenar por"), "nome-desc");

    expect(nomesNaTela()).toEqual(["Gama", "Beta", "Alfa"]);
  });
});

describe("ArvoreDePastas: filtro de pastas", () => {
  const filtro = () => screen.getByRole("searchbox", { name: "Filtrar pastas" });

  it("filtra a árvore e mantém o caminho até a pasta encontrada", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    await userEvent.type(filtro(), "fundacao");

    const arvore = screen.getByRole("tree", { name: "Pastas" });
    expect(within(arvore).getByRole("button", { name: "Abrir a pasta Fundação" })).toBeVisible();
    expect(within(arvore).getByRole("button", { name: "Abrir a pasta Obras" })).toBeVisible();
    expect(within(arvore).queryByRole("button", { name: "Abrir a pasta Laboratório" })).toBeNull();
  });

  it("expande ramos recolhidos enquanto filtra", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");
    await userEvent.click(screen.getByRole("button", { name: "Recolher Obras" }));
    const arvore = screen.getByRole("tree", { name: "Pastas" });
    expect(within(arvore).queryByRole("button", { name: "Abrir a pasta Fundação" })).toBeNull();

    await userEvent.type(filtro(), "fund");

    expect(within(arvore).getByRole("button", { name: "Abrir a pasta Fundação" })).toBeVisible();
  });

  it("sem pasta que combine, avisa e mantém 'Todos os formulários'", async () => {
    renderizar(null);
    await screen.findByText("Sem pasta");

    await userEvent.type(filtro(), "zzz");

    expect(screen.getByText(/Nenhuma pasta com «zzz»/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir Todos os formulários" })).toBeVisible();
  });

  it("sem nenhuma pasta criada, o filtro não aparece", async () => {
    renderizar(null, { listarPastas: async () => [], listarFormularios: async () => [] });
    await screen.findByText(/Nenhum formulário ainda/);

    expect(screen.queryByRole("searchbox", { name: "Filtrar pastas" })).not.toBeInTheDocument();
  });
});
