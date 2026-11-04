import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Campo, Esquemas, FormularioDetalhe, ResumoDeFormulario } from "../api/cliente";
import { clienteFalso, renderizarComApi } from "../test/clienteFalso";
import { PaginaDoMapa } from "./PaginaDoMapa";

type Coluna = Esquemas["ColunaSaida"];

const resumo = (id: number, nome: string): ResumoDeFormulario => ({
  id,
  nome,
  criado_em: "2026-11-02T10:00:00+00:00",
  versao_atual_id: id * 10,
  versao_atual_numero: 1,
  pasta_id: null,
});

const detalhe = (id: number, nome: string, campos: Campo[]) =>
  ({
    id,
    nome,
    criado_em: "x",
    versao_atual: { id: id * 10, numero: 1, definicao: { campos } },
  }) as unknown as FormularioDetalhe;

const coluna = (id: string, tipo: Coluna["tipo"], extra: Partial<Coluna> = {}): Coluna => ({
  id,
  rotulo: id,
  tipo,
  unidade: null,
  casas_decimais: null,
  resultado: null,
  opcoes: [],
  filtravel: false,
  ...extra,
});

const registro = (id: number, formulario_id: number, dados: Record<string, unknown>) => ({
  id,
  formulario_id,
  versao_id: formulario_id * 10,
  dados,
  criado_em: "2026-11-02T10:00:00+00:00",
  atualizado_em: "x",
});

const ENSAIO: Campo[] = [
  { id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%", compartilhado: true },
];
const PROCTOR: Campo[] = [
  { id: "ensaio", tipo: "referencia", rotulo: "Ensaio de origem", formulario: "Ensaio" },
  { id: "ok", tipo: "calculado", rotulo: "Conforme?" },
];

function cliente(extra = {}) {
  return clienteFalso({
    listarFormularios: async () => [resumo(1, "Ensaio"), resumo(2, "Proctor")],
    obterFormulario: async (id: number) =>
      id === 1 ? detalhe(1, "Ensaio", ENSAIO) : detalhe(2, "Proctor", PROCTOR),
    listarVersoes: async (id: number) => [{ id: id * 10, numero: 1, publicada_em: "x" }],
    listarRegistros: async (id: number) =>
      id === 1
        ? {
            versao_id: 10,
            total: 1,
            colunas: [coluna("umidade", "numero", { rotulo: "Umidade", unidade: "%" })],
            itens: [registro(5, 1, { umidade: "12.4" })],
          }
        : {
            versao_id: 20,
            total: 1,
            colunas: [
              coluna("ensaio", "referencia", { rotulo: "Ensaio de origem" }),
              coluna("ok", "calculado", { rotulo: "Conforme?", resultado: "booleano" }),
            ],
            itens: [registro(8, 2, { ensaio: 5, ok: { valor: false, erro: null } })],
          },
    ...extra,
  });
}

describe("PaginaDoMapa", () => {
  it("mostra os formulários como cartões ligados pela referência", async () => {
    renderizarComApi(<PaginaDoMapa navegar={vi.fn()} />, cliente());

    expect(await screen.findByRole("button", { name: /^Formulário Ensaio/ })).toBeInTheDocument();
    const proctor = screen.getByRole("button", { name: /^Formulário Proctor/ });
    expect(within(proctor).getByText("Ensaio de origem")).toBeInTheDocument();
  });

  it("selecionar um cartão abre o inspetor com de quem recebe e quem usa", async () => {
    renderizarComApi(<PaginaDoMapa navegar={vi.fn()} />, cliente());
    await userEvent.click(await screen.findByRole("button", { name: /^Formulário Proctor/ }));

    const inspetor = screen.getByLabelText("Detalhes do cartão selecionado");
    expect(within(inspetor).getByRole("heading", { name: "Proctor" })).toBeInTheDocument();
    expect(within(inspetor).getByText("via Ensaio de origem")).toBeInTheDocument();
  });

  it("do inspetor dá para saltar para o cartão vizinho", async () => {
    renderizarComApi(<PaginaDoMapa navegar={vi.fn()} />, cliente());
    await userEvent.click(await screen.findByRole("button", { name: /^Formulário Proctor/ }));
    const inspetor = screen.getByLabelText("Detalhes do cartão selecionado");

    await userEvent.click(within(inspetor).getByRole("button", { name: /Ensaio/ }));

    expect(within(inspetor).getByRole("heading", { name: "Ensaio" })).toBeInTheDocument();
    expect(within(inspetor).getByText("Proctor")).toBeInTheDocument();
  });

  it("as ações do inspetor navegam", async () => {
    const navegar = vi.fn();
    renderizarComApi(<PaginaDoMapa navegar={navegar} />, cliente());
    await userEvent.click(await screen.findByRole("button", { name: /^Formulário Proctor/ }));

    await userEvent.click(screen.getByRole("button", { name: "Registros" }));
    await userEvent.click(screen.getByRole("button", { name: "Novo registro" }));

    expect(navegar.mock.calls.map(([rota]) => rota)).toEqual([
      { nome: "registros", formularioId: 2 },
      { nome: "novoRegistro", formularioId: 2 },
    ]);
  });

  it("no nível dos registros mostra os valores e a conformidade", async () => {
    renderizarComApi(<PaginaDoMapa navegar={vi.fn()} />, cliente());
    await screen.findByRole("button", { name: /^Formulário Ensaio/ });

    await userEvent.click(screen.getByRole("button", { name: "Registros e valores" }));

    const ensaio = screen.getByRole("button", { name: "Registro 5 de Ensaio" });
    expect(within(ensaio).getByText("12,4")).toBeInTheDocument();
    const proctor = screen.getByRole("button", { name: "Registro 8 de Proctor" });
    expect(within(proctor).getByText("Não")).toBeInTheDocument();
  });

  it("selecionar um registro apaga os que não fazem parte da cadeia", async () => {
    renderizarComApi(
      <PaginaDoMapa navegar={vi.fn()} />,
      cliente({
        listarRegistros: async (id: number) =>
          id === 1
            ? {
                versao_id: 10,
                total: 2,
                colunas: [coluna("umidade", "numero")],
                itens: [registro(5, 1, { umidade: "1" }), registro(6, 1, { umidade: "2" })],
              }
            : {
                versao_id: 20,
                total: 1,
                colunas: [coluna("ensaio", "referencia")],
                itens: [registro(8, 2, { ensaio: 5 })],
              },
      }),
    );
    await screen.findByRole("button", { name: /^Formulário Ensaio/ });
    await userEvent.click(screen.getByRole("button", { name: "Registros e valores" }));
    // o 6 não tem vínculo: só aparece com "Incluir sem vínculo"
    await userEvent.click(screen.getByRole("checkbox", { name: "Incluir sem vínculo" }));
    expect(screen.getByRole("button", { name: "Registro 6 de Ensaio" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Registro 8 de Proctor" }));

    const cartaoFora = screen.getByRole("button", { name: "Registro 6 de Ensaio" }).parentElement;
    const cartaoDentro = screen.getByRole("button", { name: "Registro 5 de Ensaio" }).parentElement;
    expect(cartaoFora).toHaveClass("opacity-35");
    expect(cartaoDentro).not.toHaveClass("opacity-35");
  });

  it("sem nenhuma referência, orienta a criar uma", async () => {
    renderizarComApi(
      <PaginaDoMapa navegar={vi.fn()} />,
      cliente({
        obterFormulario: async (id: number) => detalhe(id, id === 1 ? "Ensaio" : "Proctor", []),
      }),
    );

    expect(
      await screen.findByText(/Nenhum formulário aponta para outro ainda/),
    ).toBeInTheDocument();
  });

  it("sem formulários, mostra o estado vazio", async () => {
    renderizarComApi(
      <PaginaDoMapa navegar={vi.fn()} />,
      clienteFalso({ listarFormularios: async () => [] }),
    );

    expect(await screen.findByText("Nada para mapear ainda")).toBeInTheDocument();
  });

  it("avisa quando os registros foram cortados pelo limite", async () => {
    renderizarComApi(
      <PaginaDoMapa navegar={vi.fn()} />,
      cliente({
        listarRegistros: async () => ({
          versao_id: 10,
          total: 999,
          colunas: [],
          itens: [registro(5, 1, {})],
        }),
      }),
    );

    expect(
      await screen.findByText(/Mostrando só os registros mais recentes de/),
    ).toBeInTheDocument();
  });

  it("mostra a falha de carregamento em português", async () => {
    renderizarComApi(
      <PaginaDoMapa navegar={vi.fn()} />,
      clienteFalso({
        listarFormularios: async () => {
          throw new Error("sem rede");
        },
      }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
