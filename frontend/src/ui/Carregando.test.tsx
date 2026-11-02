import { act, render, screen } from "@testing-library/react";
import { Carregando, Esqueleto } from ".";

describe("Carregando", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("não mostra nada nos primeiros instantes, para uma resposta rápida não piscar", () => {
    render(
      <Carregando rotulo="Carregando formulários">
        <Esqueleto />
      </Carregando>,
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("depois do atraso mostra o esqueleto, avisando o leitor de tela que está ocupado", () => {
    render(
      <Carregando rotulo="Carregando formulários" atrasoMs={150}>
        <Esqueleto />
      </Carregando>,
    );

    act(() => vi.advanceTimersByTime(150));

    const area = screen.getByRole("status", { name: "Carregando formulários" });
    expect(area).toHaveAttribute("aria-busy", "true");
  });

  it("com atraso zero aparece de imediato", () => {
    render(
      <Carregando rotulo="Carregando" atrasoMs={0}>
        <Esqueleto />
      </Carregando>,
    );

    expect(screen.getByRole("status", { name: "Carregando" })).toBeInTheDocument();
  });

  it("se o dado chega antes do atraso, o esqueleto nunca aparece", () => {
    const { unmount } = render(
      <Carregando rotulo="Carregando">
        <Esqueleto />
      </Carregando>,
    );

    unmount();
    act(() => vi.advanceTimersByTime(500));

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("os blocos do esqueleto ficam escondidos do leitor de tela", () => {
    const { container } = render(
      <Carregando rotulo="Carregando" atrasoMs={0}>
        <Esqueleto />
      </Carregando>,
    );

    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });
});
