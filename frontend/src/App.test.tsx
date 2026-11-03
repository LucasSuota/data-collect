import { render, screen } from "@testing-library/react";
import { App } from "./App";
import { ApiProvider } from "./api/contexto";
import { clienteFalso } from "./test/clienteFalso";

function renderizar(hash: string) {
  window.location.hash = hash;
  return render(
    <ApiProvider
      cliente={clienteFalso({ listarFormularios: async () => [], listarPastas: async () => [] })}
    >
      <App />
    </ApiProvider>,
  );
}

describe("App", () => {
  afterEach(() => {
    window.location.hash = "";
  });

  it("mostra o título da aplicação e, na raiz, a lista de formulários", async () => {
    renderizar("#/");

    expect(screen.getByRole("link", { name: "data-collect" })).toBeInTheDocument();
    // Espera a lista carregar: durante o esqueleto o título existe, mas é trocado em seguida.
    expect(await screen.findByText("Nenhum formulário ainda")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Formulários" })).toBeInTheDocument();
  });

  it("uma rota desconhecida mostra a página não encontrada com o caminho de volta", () => {
    renderizar("#/nada");

    expect(screen.getByText(/Página não encontrada/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voltar aos formulários" })).toHaveAttribute(
      "href",
      "#/",
    );
  });
});
