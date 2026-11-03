import { act, renderHook } from "@testing-library/react";
import { useMovimentoReduzido } from "./movimentoReduzido";

function simularMatchMedia(inicial: boolean) {
  const ouvintes = new Set<() => void>();
  const consulta = {
    matches: inicial,
    addEventListener: (_: string, f: () => void) => ouvintes.add(f),
    removeEventListener: (_: string, f: () => void) => ouvintes.delete(f),
  };
  vi.stubGlobal("matchMedia", () => consulta);
  return {
    mudarPara(valor: boolean) {
      consulta.matches = valor;
      ouvintes.forEach((f) => f());
    },
  };
}

describe("useMovimentoReduzido", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sem matchMedia (ambiente sem suporte), assume movimento normal", () => {
    vi.stubGlobal("matchMedia", undefined);

    const { result } = renderHook(() => useMovimentoReduzido());

    expect(result.current).toBe(false);
  });

  it("lê a preferência do sistema", () => {
    simularMatchMedia(true);

    const { result } = renderHook(() => useMovimentoReduzido());

    expect(result.current).toBe(true);
  });

  it("acompanha a mudança de preferência enquanto o app está aberto", () => {
    const sistema = simularMatchMedia(false);
    const { result } = renderHook(() => useMovimentoReduzido());

    act(() => sistema.mudarPara(true));

    expect(result.current).toBe(true);
  });
});
