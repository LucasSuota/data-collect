import type { Esquemas } from "../api/cliente";
import { baixarArquivo, formatarCelula } from "./formatacao";

type Coluna = Esquemas["ColunaSaida"];

const coluna = (parcial: Partial<Coluna> & Pick<Coluna, "tipo">): Coluna => ({
  id: "c",
  rotulo: "C",
  unidade: null,
  casas_decimais: null,
  resultado: null,
  opcoes: [],
  filtravel: false,
  ...parcial,
});

describe("formatarCelula", () => {
  it("número arredonda só na exibição, com vírgula", () => {
    expect(formatarCelula(coluna({ tipo: "numero", casas_decimais: 1 }), "25.46")).toBe("25,5");
    expect(formatarCelula(coluna({ tipo: "numero" }), "25.4647")).toBe("25,4647");
  });

  it("calculado usa o tipo do resultado informado pelo servidor", () => {
    const numerico = coluna({ tipo: "calculado", resultado: "numero", casas_decimais: 1 });
    const booleano = coluna({ tipo: "calculado", resultado: "booleano" });
    const data = coluna({ tipo: "calculado", resultado: "data" });

    expect(formatarCelula(numerico, { valor: "25.46479", erro: null })).toBe("25,5");
    expect(formatarCelula(booleano, { valor: true, erro: null })).toBe("Sim");
    expect(formatarCelula(booleano, { valor: false, erro: null })).toBe("Não");
    expect(formatarCelula(data, { valor: "2026-11-29", erro: null })).toBe("29/11/2026");
  });

  it("calculado com erro mostra o erro; vazio ou ausente mostra traço", () => {
    const c = coluna({ tipo: "calculado", resultado: "numero" });

    expect(formatarCelula(c, { valor: null, erro: "Divisão por zero." })).toBe(
      "ERRO: Divisão por zero.",
    );
    expect(formatarCelula(c, { valor: null, erro: null })).toBe("—");
    expect(formatarCelula(c, undefined)).toBe("—");
  });

  it("sim/não, data, referência, localização e foto", () => {
    expect(formatarCelula(coluna({ tipo: "sim_nao" }), true)).toBe("Sim");
    expect(formatarCelula(coluna({ tipo: "sim_nao" }), false)).toBe("Não");
    expect(formatarCelula(coluna({ tipo: "data" }), "2026-11-01")).toBe("01/11/2026");
    expect(formatarCelula(coluna({ tipo: "referencia" }), 12)).toBe("#12");
    expect(
      formatarCelula(coluna({ tipo: "localizacao" }), { latitude: "-23.55", longitude: "-46.63" }),
    ).toBe("-23,55 / -46,63");
    expect(formatarCelula(coluna({ tipo: "foto" }), [1, 2, 3])).toBe("3 foto(s)");
  });

  it("texto e seleção saem como estão; vazio sai vazio", () => {
    expect(formatarCelula(coluna({ tipo: "texto" }), "obra A")).toBe("obra A");
    expect(formatarCelula(coluna({ tipo: "selecao" }), "Aprovado")).toBe("Aprovado");
    for (const tipo of [
      "texto",
      "numero",
      "data",
      "sim_nao",
      "referencia",
      "localizacao",
      "foto",
    ] as const) {
      expect(formatarCelula(coluna({ tipo }), null)).toBe("");
    }
  });

  it("é texto puro: nada de HTML interpretado", () => {
    expect(formatarCelula(coluna({ tipo: "texto" }), "<b>x</b>")).toBe("<b>x</b>");
  });
});

describe("baixarArquivo", () => {
  it("cria um link temporário com o nome do arquivo, clica nele e limpa a URL", () => {
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    URL.createObjectURL = vi.fn(() => "blob:csv");
    URL.revokeObjectURL = vi.fn();
    let baixado: { href: string; download: string } | null = null;
    clique.mockImplementation(function (this: HTMLAnchorElement) {
      baixado = { href: this.href, download: this.download };
    });

    baixarArquivo({ blob: new Blob(["a;b"]), nome: "corpo.csv" });

    expect(baixado).toEqual({ href: "blob:csv", download: "corpo.csv" });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:csv");
    expect(document.querySelector("a[download]")).toBeNull();
    clique.mockRestore();
  });
});
