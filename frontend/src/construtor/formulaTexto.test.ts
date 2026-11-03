import {
  analisarParenteses,
  argumentoAtivo,
  argumentosDaAssinatura,
  aoApagar,
  aoDigitar,
  chamadaNoCursor,
  parDoCursor,
} from "./formulaTexto";

describe("analisarParenteses", () => {
  it("casa cada abre com o seu fecha, respeitando o aninhamento", () => {
    expect(analisarParenteses("a * (b + (c))")).toEqual({
      pares: [
        [9, 11],
        [4, 12],
      ],
      semPar: [],
    });
  });

  it("aponta o parêntese que abre sem fechar", () => {
    expect(analisarParenteses("(a + (b)")).toEqual({ pares: [[5, 7]], semPar: [0] });
  });

  it("aponta o parêntese que fecha sem abrir", () => {
    expect(analisarParenteses("a + b)")).toEqual({ pares: [], semPar: [5] });
  });

  it("texto sem parênteses não tem nada a apontar", () => {
    expect(analisarParenteses("a + 1")).toEqual({ pares: [], semPar: [] });
  });
});

describe("parDoCursor", () => {
  const texto = "(a + b) * c";

  it("com o cursor logo depois de um parêntese, devolve o par dele", () => {
    expect(parDoCursor(texto, 7)).toEqual([0, 6]);
    expect(parDoCursor(texto, 1)).toEqual([0, 6]);
  });

  it("com o cursor logo antes de um parêntese que não tem outro ao lado, usa o da frente", () => {
    expect(parDoCursor(texto, 0)).toEqual([0, 6]);
  });

  it("longe de qualquer parêntese, não há par", () => {
    expect(parDoCursor(texto, 4)).toBeNull();
  });

  it("parêntese sem par não destaca nada", () => {
    expect(parDoCursor("(a + b", 1)).toBeNull();
  });
});

describe("chamadaNoCursor", () => {
  it("acha a função em que o cursor está e o argumento atual", () => {
    expect(chamadaNoCursor("soma(a, b", 9)).toEqual({ nome: "soma", argumento: 1 });
    expect(chamadaNoCursor("soma(", 5)).toEqual({ nome: "soma", argumento: 0 });
  });

  it("numa chamada aninhada, vale a mais interna", () => {
    expect(chamadaNoCursor("soma(a, se(b, ", 14)).toEqual({ nome: "se", argumento: 1 });
  });

  it("depois de fechar a interna, volta para a de fora", () => {
    expect(chamadaNoCursor("soma(a, se(b, c, d), ", 21)).toEqual({ nome: "soma", argumento: 2 });
  });

  it("vírgula dentro de um agrupamento não conta como outro argumento", () => {
    expect(chamadaNoCursor("max(1, (2 + 3), ", 16)).toEqual({ nome: "max", argumento: 2 });
  });

  it("parêntese de agrupamento (sem nome de função) é ignorado: vale a função de fora", () => {
    expect(chamadaNoCursor("soma(1, (2 + ", 13)).toEqual({ nome: "soma", argumento: 1 });
  });

  it("fora de qualquer função, não há chamada", () => {
    expect(chamadaNoCursor("a + (b * c", 10)).toBeNull();
    expect(chamadaNoCursor("soma(a)", 7)).toBeNull();
    expect(chamadaNoCursor("", 0)).toBeNull();
  });

  it("só considera o texto antes do cursor", () => {
    // A vírgula e o `b` vêm depois do cursor: não contam.
    expect(chamadaNoCursor("soma(a, b)", 6)).toEqual({ nome: "soma", argumento: 0 });
    expect(chamadaNoCursor("soma(a, b)", 9)).toEqual({ nome: "soma", argumento: 1 });
  });
});

describe("argumentosDaAssinatura", () => {
  it("separa os argumentos da assinatura do catálogo", () => {
    expect(argumentosDaAssinatura("se(cond, a, b)")).toEqual(["cond", "a", "b"]);
  });

  it("função sem argumentos e variádica", () => {
    expect(argumentosDaAssinatura("agora()")).toEqual([]);
    expect(argumentosDaAssinatura("soma(a, b, ...)")).toEqual(["a", "b", "..."]);
  });

  it("texto que não parece uma assinatura não gera argumentos", () => {
    expect(argumentosDaAssinatura("pi")).toEqual([]);
  });
});

describe("argumentoAtivo", () => {
  it("é o próprio índice quando ele existe na assinatura", () => {
    expect(argumentoAtivo(["cond", "a", "b"], 1)).toBe(1);
  });

  it("em função variádica, os argumentos que passam do fim caem no `...`", () => {
    expect(argumentoAtivo(["a", "b", "..."], 5)).toBe(2);
  });

  it("passou do número de argumentos de uma função fixa: nenhum fica em destaque", () => {
    expect(argumentoAtivo(["n"], 2)).toBeNull();
  });
});

describe("aoDigitar", () => {
  it("abrir parêntese insere o par e deixa o cursor no meio", () => {
    expect(aoDigitar("1 + ", 4, 4, "(")).toEqual({ texto: "1 + ()", cursor: 5 });
  });

  it("não fecha sozinho quando o parêntese vem colado numa palavra", () => {
    expect(aoDigitar("soma", 0, 0, "(")).toBeNull();
  });

  it("não interfere quando há trecho selecionado", () => {
    expect(aoDigitar("a + b", 0, 5, "(")).toBeNull();
  });

  it("fechar parêntese quando o próximo já é `)` só avança o cursor", () => {
    expect(aoDigitar("(a)", 2, 2, ")")).toEqual({ texto: "(a)", cursor: 3 });
  });

  it("fechar parêntese sem `)` na frente escreve normalmente", () => {
    expect(aoDigitar("(a", 2, 2, ")")).toBeNull();
  });

  it("outras teclas seguem o fluxo normal", () => {
    expect(aoDigitar("a", 1, 1, "+")).toBeNull();
  });
});

describe("aoApagar", () => {
  it("apagar entre `(` e `)` remove o par inteiro", () => {
    expect(aoApagar("soma()", 5)).toEqual({ texto: "soma", cursor: 4 });
  });

  it("apagar um parêntese que não está vazio segue o fluxo normal", () => {
    expect(aoApagar("soma(a)", 6)).toBeNull();
    expect(aoApagar("soma(", 5)).toBeNull();
  });
});
