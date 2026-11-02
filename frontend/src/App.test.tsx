import { render, screen } from "@testing-library/react";
import { App } from "./App";

describe("App", () => {
  it("mostra o título da aplicação em português", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Construtor de Formulários" })).toBeInTheDocument();
  });
});
