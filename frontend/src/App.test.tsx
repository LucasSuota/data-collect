import { render, screen } from "@testing-library/react";
import { App } from "./App";
import { ApiProvider } from "./api/contexto";
import { clienteFalso } from "./test/clienteFalso";
import { ComSessao } from "./test/sessaoFalsa";

const TECNICO = [
  "formularios:ver",
  "registros:ver",
  "registros:criar",
  "registros:editar_proprios",
];
const ADMIN = [...TECNICO, "equipe:ver", "cargos:editar", "formularios:publicar", "ia:assistente"];

function renderizar(hash: string, permissoes: string[] = ADMIN) {
  window.location.hash = hash;
  return render(
    <ApiProvider
      cliente={clienteFalso({
        listarFormularios: async () => [],
        listarPastas: async () => [],
        registrosRecentes: async () => [],
        notificacoes: async () => ({ itens: [], nao_lidas: 0 }),
        progresso: async () => ({ tour_concluido: true, passo: 0, checklist_dispensado: true }),
        listarMembros: async () => [],
      })}
    >
      <ComSessao permissoes={permissoes}>
        <App />
      </ComSessao>
    </ApiProvider>,
  );
}

describe("App", () => {
  afterEach(() => {
    window.location.hash = "";
  });

  it("na raiz mostra o início com a saudação e o cargo", async () => {
    renderizar("#/");

    expect(await screen.findByRole("heading", { name: "Olá, Lucas" })).toBeInTheDocument();
    expect(screen.getAllByText("Teste").length).toBeGreaterThan(0);
  });

  it("a lista de formulários fica em #/formularios", async () => {
    renderizar("#/formularios");

    expect(await screen.findByText("Nenhum formulário ainda")).toBeInTheDocument();
  });

  it("uma rota desconhecida mostra a página não encontrada com o caminho de volta", () => {
    renderizar("#/nada");

    expect(screen.getByText(/Página não encontrada/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar ao início" })).toHaveAttribute("href", "#/");
  });

  it("a navegação deriva das permissões: o técnico não vê Equipe nem Cargos", () => {
    renderizar("#/nada", TECNICO);

    const menu = screen.getAllByRole("navigation", { name: "Principal" })[0]!;
    expect(menu).toHaveTextContent("Registros");
    expect(menu).not.toHaveTextContent("Equipe");
    expect(menu).not.toHaveTextContent("Cargos e permissões");
  });

  it("quem tem as permissões de administração vê Equipe e Cargos", () => {
    renderizar("#/nada", ADMIN);

    const menu = screen.getAllByRole("navigation", { name: "Principal" })[0]!;
    expect(menu).toHaveTextContent("Equipe");
    expect(menu).toHaveTextContent("Cargos e permissões");
  });
});
