import {
  caminhoAte,
  destinosDeMovimento,
  idsDaSubarvore,
  montarArvore,
  anunciosDeArraste,
  resolverMovimento,
  type Pasta,
} from "./pastas";

const pasta = (id: number, nome: string, pasta_pai_id: number | null = null): Pasta => ({
  id,
  nome,
  pasta_pai_id,
  criado_em: "2026-11-02T10:00:00+00:00",
});

const OBRAS = pasta(1, "Obras");
const LAB = pasta(2, "Laboratório");
const FUNDACAO = pasta(3, "Fundação", 1);
const ESTACAS = pasta(4, "Estacas", 3);

describe("montarArvore", () => {
  it("monta a árvore a partir da lista plana", () => {
    const arvore = montarArvore([OBRAS, FUNDACAO, ESTACAS, LAB]);

    expect(arvore.map((no) => no.pasta.nome)).toEqual(["Laboratório", "Obras"]);
    const obras = arvore.find((no) => no.pasta.id === 1);
    expect(obras?.filhos.map((no) => no.pasta.nome)).toEqual(["Fundação"]);
    expect(obras?.filhos[0]?.filhos.map((no) => no.pasta.nome)).toEqual(["Estacas"]);
  });

  it("ordena os irmãos por nome, sem diferenciar caixa nem acento", () => {
    const arvore = montarArvore([pasta(1, "zebra"), pasta(2, "Água"), pasta(3, "abacaxi")]);

    expect(arvore.map((no) => no.pasta.nome)).toEqual(["abacaxi", "Água", "zebra"]);
  });

  it("uma pasta cujo pai não está na lista vai para a raiz, em vez de sumir", () => {
    const arvore = montarArvore([pasta(5, "Órfã", 99)]);

    expect(arvore.map((no) => no.pasta.nome)).toEqual(["Órfã"]);
  });

  it("lista vazia dá árvore vazia", () => {
    expect(montarArvore([])).toEqual([]);
  });
});

describe("caminhoAte", () => {
  const todas = [OBRAS, LAB, FUNDACAO, ESTACAS];

  it("devolve as pastas da raiz até a pedida", () => {
    expect(caminhoAte(todas, 4).map((p) => p.nome)).toEqual(["Obras", "Fundação", "Estacas"]);
  });

  it("para a raiz (nulo) o caminho é vazio", () => {
    expect(caminhoAte(todas, null)).toEqual([]);
  });

  it("pasta inexistente dá caminho vazio", () => {
    expect(caminhoAte(todas, 99)).toEqual([]);
  });
});

describe("idsDaSubarvore", () => {
  it("inclui a própria pasta e todas as descendentes", () => {
    expect(idsDaSubarvore([OBRAS, LAB, FUNDACAO, ESTACAS], 1)).toEqual(new Set([1, 3, 4]));
  });

  it("uma folha só tem a si mesma", () => {
    expect(idsDaSubarvore([OBRAS, FUNDACAO], 3)).toEqual(new Set([3]));
  });
});

describe("destinosDeMovimento", () => {
  const todas = [OBRAS, LAB, FUNDACAO, ESTACAS];

  it("lista as pastas com o caminho completo, em ordem de árvore", () => {
    expect(destinosDeMovimento(todas).map((d) => d.rotulo)).toEqual([
      "Laboratório",
      "Obras",
      "Obras / Fundação",
      "Obras / Fundação / Estacas",
    ]);
  });

  it("ao mover uma pasta, esconde ela e suas descendentes (cairia num ciclo)", () => {
    const destinos = destinosDeMovimento(todas, 1);

    expect(destinos.map((d) => d.id)).toEqual([2]);
  });
});

describe("resolverMovimento", () => {
  it("formulário solto numa pasta vira movimento para ela", () => {
    expect(resolverMovimento("formulario-7", "pasta-3")).toEqual({ formularioId: 7, pastaId: 3 });
  });

  it("solto na raiz leva o formulário à raiz", () => {
    expect(resolverMovimento("formulario-7", "pasta-raiz")).toEqual({
      formularioId: 7,
      pastaId: null,
    });
  });

  it("solto fora de qualquer destino não move nada", () => {
    expect(resolverMovimento("formulario-7", null)).toBeNull();
  });

  it("ids que não são de formulário ou de pasta são ignorados", () => {
    expect(resolverMovimento("campo-1", "pasta-3")).toBeNull();
    expect(resolverMovimento("formulario-7", "outra-coisa")).toBeNull();
    expect(resolverMovimento("formulario-x", "pasta-3")).toBeNull();
  });
});

describe("anunciosDeArraste", () => {
  const nomes = {
    formulario: (id: string) => (id === "formulario-7" ? "Sondagem" : null),
    destino: (id: string) =>
      id === "pasta-1" ? "Obras" : id === "pasta-raiz" ? "Todos os formulários" : null,
  };
  const anuncios = anunciosDeArraste(nomes);

  it("anuncia, em português, o formulário pego", () => {
    expect(anuncios.onDragStart({ active: { id: "formulario-7" } })).toBe(
      "Você pegou o formulário Sondagem.",
    );
  });

  it("anuncia sobre qual pasta o formulário está", () => {
    expect(anuncios.onDragOver({ active: { id: "formulario-7" }, over: { id: "pasta-1" } })).toBe(
      "O formulário Sondagem está sobre a pasta Obras.",
    );
  });

  it("anuncia quando não está sobre nenhuma pasta", () => {
    expect(anuncios.onDragOver({ active: { id: "formulario-7" }, over: null })).toBe(
      "O formulário Sondagem não está sobre nenhuma pasta.",
    );
  });

  it("anuncia onde o formulário foi solto, e quando o movimento foi cancelado", () => {
    expect(anuncios.onDragEnd({ active: { id: "formulario-7" }, over: { id: "pasta-1" } })).toBe(
      "O formulário Sondagem foi solto na pasta Obras.",
    );
    expect(anuncios.onDragEnd({ active: { id: "formulario-7" }, over: null })).toBe(
      "O formulário Sondagem foi solto fora de uma pasta. Nada mudou.",
    );
    expect(anuncios.onDragCancel({ active: { id: "formulario-7" } })).toBe(
      "Movimento cancelado. O formulário Sondagem ficou onde estava.",
    );
  });

  it("id desconhecido não gera anúncio", () => {
    expect(anuncios.onDragStart({ active: { id: "outra-coisa" } })).toBeUndefined();
  });
});
