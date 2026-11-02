import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ErroDaApi, type Esquemas } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaDeRegistros } from "./PaginaDeRegistros";

type Coluna = Esquemas["ColunaSaida"];

const coluna = (parcial: Partial<Coluna> & Pick<Coluna, "id" | "tipo">): Coluna => ({
  rotulo: parcial.id,
  unidade: null,
  casas_decimais: null,
  resultado: null,
  opcoes: [],
  filtravel: false,
  ...parcial,
});

const COLUNAS: Coluna[] = [
  coluna({
    id: "fase",
    tipo: "selecao",
    rotulo: "Fase",
    opcoes: ["Cura", "Ruptura"],
    filtravel: true,
  }),
  coluna({ id: "carga", tipo: "numero", rotulo: "Carga", unidade: "kN", casas_decimais: 1 }),
  coluna({ id: "obs", tipo: "texto", rotulo: "Observação", filtravel: true }),
  coluna({ id: "ok", tipo: "sim_nao", rotulo: "Ensaiado?", filtravel: true }),
  coluna({
    id: "conforme",
    tipo: "calculado",
    rotulo: "Conforme?",
    resultado: "booleano",
    filtravel: true,
  }),
  coluna({
    id: "dobro",
    tipo: "calculado",
    rotulo: "Dobro",
    resultado: "numero",
    casas_decimais: 1,
  }),
];

const registro = (id: number, dados: Record<string, unknown> = {}) => ({
  id,
  formulario_id: 3,
  versao_id: 31,
  dados: {
    fase: "Cura",
    carga: "25.46",
    obs: `obs ${id}`,
    ok: true,
    conforme: { valor: true, erro: null },
    dobro: { valor: "50.92", erro: null },
    ...dados,
  },
  criado_em: "2026-11-02T10:00:00+00:00",
  atualizado_em: "x",
});

const pagina = (itens: ReturnType<typeof registro>[], total = itens.length, versao_id = 31) => ({
  versao_id,
  colunas: COLUNAS,
  itens,
  total,
});

const formulario = {
  id: 3,
  nome: "Corpo de prova",
  criado_em: "x",
  versao_atual: {
    id: 31,
    formulario_id: 3,
    numero: 2,
    definicao: { campos: [] },
    publicada_em: "x",
  },
};
const versoes = [
  { id: 30, numero: 1, publicada_em: "x" },
  { id: 31, numero: 2, publicada_em: "x" },
];

function renderizar(listarRegistros = vi.fn(async () => pagina([registro(1)])), extra = {}) {
  const navegar = vi.fn();
  renderizarComApi(
    <PaginaDeRegistros formularioId={3} navegar={navegar} />,
    clienteFalso({
      obterFormulario: async () => formulario,
      listarVersoes: async () => versoes,
      listarRegistros,
      ...extra,
    }),
  );
  return { listarRegistros, navegar };
}

describe("PaginaDeRegistros", () => {
  it("mostra as colunas da definição com unidade e as células formatadas", async () => {
    renderizar();

    expect(await screen.findByRole("columnheader", { name: "Carga (kN)" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Fase" })).toBeInTheDocument();
    const linha = screen.getByRole("row", { name: /obs 1/ });
    expect(within(linha).getByText("25,5")).toBeInTheDocument(); // casas_decimais só na exibição
    expect(within(linha).getByText("50,9")).toBeInTheDocument();
    expect(within(linha).getAllByText("Sim")).toHaveLength(2); // sim/não e o calculado booleano
    expect(
      await screen.findByRole("heading", { name: "Registros · Corpo de prova" }),
    ).toBeInTheDocument();
  });

  it("mostra o erro do calculado na própria célula", async () => {
    renderizar(
      vi.fn(async () =>
        pagina([registro(1, { dobro: { valor: null, erro: "Divisão por zero." } })]),
      ),
    );

    expect(await screen.findByText("ERRO: Divisão por zero.")).toBeInTheDocument();
  });

  it("sem registros mostra a mensagem em vez de uma tabela vazia", async () => {
    renderizar(vi.fn(async () => pagina([], 0)));

    expect(await screen.findByText("Nenhum registro encontrado.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("abre um registro (que será editado com a definição da versão dele)", async () => {
    const { navegar } = renderizar();

    await userEvent.click(await screen.findByRole("button", { name: "Abrir o registro 1" }));

    expect(navegar).toHaveBeenCalledWith({ nome: "registro", registroId: 1 });
  });

  it("leva ao formulário de novo registro", async () => {
    const { navegar } = renderizar();

    await userEvent.click(await screen.findByRole("button", { name: "Novo registro" }));

    expect(navegar).toHaveBeenCalledWith({ nome: "novoRegistro", formularioId: 3 });
  });

  describe("paginação", () => {
    it("mostra o intervalo e o total, e pede a próxima janela", async () => {
      const itens = Array.from({ length: 25 }, (_, i) => registro(i + 1));
      const listarRegistros = vi.fn(async () => pagina(itens, 60));
      renderizar(listarRegistros);

      expect(await screen.findByText("Mostrando 1–25 de 60")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
      await userEvent.click(screen.getByRole("button", { name: "Próxima" }));

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ limite: 25, deslocamento: 25 }),
        ),
      );
    });

    it("na última página bloqueia a próxima", async () => {
      renderizar(vi.fn(async () => pagina([registro(1), registro(2)], 2)));

      expect(await screen.findByText("Mostrando 1–2 de 2")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Próxima" })).toBeDisabled();
    });
  });

  describe("filtros", () => {
    it("só oferece os campos que a API aceita (filtravel)", async () => {
      renderizar();

      const seletor = await screen.findByLabelText("Filtrar por");
      const opcoes = within(seletor)
        .getAllByRole("option")
        .map((o) => o.textContent);

      expect(opcoes).toEqual(["— campo —", "Fase", "Observação", "Ensaiado?", "Conforme?"]);
      expect(opcoes).not.toContain("Carga"); // número não filtra (guardado como string)
      expect(opcoes).not.toContain("Dobro"); // calculado numérico também não
    });

    it("filtra por seleção com as opções da definição e volta à primeira página", async () => {
      const listarRegistros = vi.fn(async () => pagina([registro(1)]));
      renderizar(listarRegistros);
      await userEvent.selectOptions(await screen.findByLabelText("Filtrar por"), "Fase");

      const valor = screen.getByLabelText("Valor do filtro");
      expect(
        within(valor)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["— valor —", "Cura", "Ruptura"]);
      await userEvent.selectOptions(valor, "Ruptura");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ filtros: { fase: "Ruptura" }, deslocamento: 0 }),
        ),
      );
      expect(screen.getByText("Fase: Ruptura")).toBeInTheDocument();
    });

    it("sim/não e calculado booleano oferecem Sim e Não e mandam true/false", async () => {
      const listarRegistros = vi.fn(async () => pagina([registro(1)]));
      renderizar(listarRegistros);
      await userEvent.selectOptions(await screen.findByLabelText("Filtrar por"), "Conforme?");

      await userEvent.selectOptions(screen.getByLabelText("Valor do filtro"), "Não");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ filtros: { conforme: "false" } }),
        ),
      );
      expect(screen.getByText("Conforme?: Não")).toBeInTheDocument();
    });

    it("texto livre; combina filtros e remove um deles", async () => {
      const listarRegistros = vi.fn(async () => pagina([registro(1)]));
      renderizar(listarRegistros);
      await userEvent.selectOptions(await screen.findByLabelText("Filtrar por"), "Observação");
      await userEvent.type(screen.getByLabelText("Valor do filtro"), "alfa");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));
      await userEvent.selectOptions(screen.getByLabelText("Filtrar por"), "Ensaiado?");
      await userEvent.selectOptions(screen.getByLabelText("Valor do filtro"), "Sim");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ filtros: { obs: "alfa", ok: "true" } }),
        ),
      );
      await userEvent.click(screen.getByRole("button", { name: "Remover o filtro Observação" }));

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ filtros: { ok: "true" } }),
        ),
      );
    });

    it("não aplica filtro sem campo ou sem valor", async () => {
      renderizar();

      const aplicar = await screen.findByRole("button", { name: "Aplicar filtro" });
      expect(aplicar).toBeDisabled();
      await userEvent.selectOptions(screen.getByLabelText("Filtrar por"), "Observação");
      expect(aplicar).toBeDisabled();
    });

    it("não mostra o filtro quando nenhuma coluna aceita", async () => {
      renderizar(
        vi.fn(async () => ({ ...pagina([registro(1)]), colunas: [COLUNAS[1] as Coluna] })),
      );

      await screen.findByRole("table");

      expect(screen.queryByLabelText("Filtrar por")).not.toBeInTheDocument();
    });
  });

  describe("datas e versão", () => {
    it("manda criado_de e criado_ate", async () => {
      const listarRegistros = vi.fn(async () => pagina([registro(1)]));
      renderizar(listarRegistros);

      await userEvent.type(await screen.findByLabelText("Criado de"), "2026-11-01");
      await userEvent.type(screen.getByLabelText("Criado até"), "2026-11-30");

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ criadoDe: "2026-11-01", criadoAte: "2026-11-30" }),
        ),
      );
    });

    it("lista as versões; trocar pede a versão escolhida e limpa os filtros", async () => {
      const listarRegistros = vi.fn(async () => pagina([registro(1)]));
      renderizar(listarRegistros);
      await userEvent.selectOptions(await screen.findByLabelText("Filtrar por"), "Observação");
      await userEvent.type(screen.getByLabelText("Valor do filtro"), "x");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));
      await screen.findByText("Observação: x");

      const seletor = screen.getByLabelText("Versão");
      expect(
        within(seletor)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["Última", "Versão 1", "Versão 2"]);
      await userEvent.selectOptions(seletor, "Versão 1");

      await waitFor(() =>
        expect(listarRegistros).toHaveBeenLastCalledWith(
          3,
          expect.objectContaining({ versaoId: 30, filtros: {} }),
        ),
      );
      expect(screen.queryByText("Observação: x")).not.toBeInTheDocument();
    });

    it("usa as colunas da versão listada", async () => {
      const antiga = [coluna({ id: "so_na_v1", tipo: "texto", rotulo: "Só na v1" })];
      const listarRegistros = vi
        .fn()
        .mockResolvedValueOnce(pagina([registro(1)]))
        .mockResolvedValue({
          versao_id: 30,
          colunas: antiga,
          itens: [registro(2, { so_na_v1: "a" })],
          total: 1,
        });
      renderizar(listarRegistros);
      await screen.findByRole("columnheader", { name: "Fase" });

      await userEvent.selectOptions(screen.getByLabelText("Versão"), "Versão 1");

      expect(await screen.findByRole("columnheader", { name: "Só na v1" })).toBeInTheDocument();
      expect(screen.queryByRole("columnheader", { name: "Fase" })).not.toBeInTheDocument();
    });
  });

  describe("exportação", () => {
    it("baixa o CSV com a mesma versão e os mesmos filtros da listagem", async () => {
      const arquivo = { blob: new Blob(["a;b"]), nome: "corpo_de_prova.csv" };
      const exportarRegistros = vi.fn(async () => arquivo);
      const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      renderizar(
        vi.fn(async () => pagina([registro(1)])),
        { exportarRegistros },
      );
      await userEvent.selectOptions(await screen.findByLabelText("Filtrar por"), "Observação");
      await userEvent.type(screen.getByLabelText("Valor do filtro"), "alfa");
      await userEvent.click(screen.getByRole("button", { name: "Aplicar filtro" }));
      await screen.findByText("Observação: alfa");

      await userEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));

      await waitFor(() => expect(clique).toHaveBeenCalled());
      expect(exportarRegistros).toHaveBeenCalledWith(
        3,
        expect.objectContaining({ filtros: { obs: "alfa" } }),
      );
      clique.mockRestore();
    });

    it("mostra o erro quando a exportação falha", async () => {
      const exportarRegistros = vi.fn(async () => {
        throw new ErroDaApi(422, "Não é possível filtrar pelo campo 'carga'.");
      });
      renderizar(
        vi.fn(async () => pagina([registro(1)])),
        { exportarRegistros },
      );

      await userEvent.click(await screen.findByRole("button", { name: "Exportar CSV" }));

      expect(await screen.findByRole("alert")).toHaveTextContent("Não é possível filtrar");
    });
  });

  it("mostra a falha de carregamento em português", async () => {
    renderizar(
      vi.fn(async () => {
        throw new ErroDaApi(404, "Formulário 3 não encontrado.");
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Formulário 3 não encontrado.");
  });
});
