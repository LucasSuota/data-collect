import {
  blocosDaFuncao,
  inserirBlocos,
  lexar,
  moverBloco,
  paraTexto,
  paresDeBlocos,
  removerBloco,
  resolverSolto,
  type Bloco,
} from "./blocos";

const CONSTANTES = ["pi"];
const textos = (blocos: Bloco[]) => blocos.map((b) => b.texto);
const tipos = (blocos: Bloco[]) => blocos.map((b) => b.tipo);

describe("lexar", () => {
  it("separa campos, números, operadores, parênteses e vírgulas", () => {
    const blocos = lexar("carga_kn * 1000 / (pi * 2)", CONSTANTES);

    expect(textos(blocos)).toEqual(["carga_kn", "*", "1000", "/", "(", "pi", "*", "2", ")"]);
    expect(tipos(blocos)).toEqual([
      "campo",
      "operador",
      "numero",
      "operador",
      "abre",
      "constante",
      "operador",
      "numero",
      "fecha",
    ]);
  });

  it("reconhece função pelo parêntese que vem logo depois do nome", () => {
    const blocos = lexar("se(a > 1, soma(b, c), 0)", CONSTANTES);

    expect(blocos.filter((b) => b.tipo === "funcao").map((b) => b.texto)).toEqual(["se", "soma"]);
    expect(blocos.filter((b) => b.tipo === "virgula")).toHaveLength(3);
  });

  it("operadores de dois caracteres ficam inteiros", () => {
    expect(textos(lexar("a ** 2 >= b != c <= d == e", CONSTANTES))).toEqual([
      "a",
      "**",
      "2",
      ">=",
      "b",
      "!=",
      "c",
      "<=",
      "d",
      "==",
      "e",
    ]);
  });

  it("and, or e not são operadores", () => {
    const blocos = lexar("a and not b or c", CONSTANTES);

    expect(tipos(blocos)).toEqual(["campo", "operador", "operador", "campo", "operador", "campo"]);
  });

  it("números decimais e com expoente são um bloco só", () => {
    expect(textos(lexar("1.5 + .5 + 2e3", CONSTANTES))).toEqual(["1.5", "+", ".5", "+", "2e3"]);
  });

  it("o que não tem bloco vira `outro` e não se perde", () => {
    const blocos = lexar("a.b + 'x'", CONSTANTES);

    expect(blocos.filter((b) => b.tipo === "outro").map((b) => b.texto)).toEqual([".", "'", "'"]);
  });

  it("guarda onde cada bloco começa e termina (em caracteres), para o erro do servidor", () => {
    const blocos = lexar("a + 😀b", CONSTANTES);

    expect(blocos.map((b) => [b.inicio, b.fim])).toEqual([
      [0, 1],
      [2, 3],
      [4, 5],
      [5, 6],
    ]);
  });

  it("texto vazio ou só espaços não tem blocos", () => {
    expect(lexar("", CONSTANTES)).toEqual([]);
    expect(lexar("   ", CONSTANTES)).toEqual([]);
  });
});

describe("paraTexto", () => {
  it.each([
    ["carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)"],
    ["se(a > 1, 1, 2)"],
    ["soma(a, b, c)"],
    ["data_moldagem + dias(28)"],
    ["-x + 3"],
    ["a - -b"],
    ["not (a and b) or c"],
    ["media(a, se(b > 0, b, 1), 2.5)"],
    ["max(1, (2 + 3), 4)"],
  ])("devolve o mesmo texto para uma fórmula já bem formatada: %s", (formula) => {
    expect(paraTexto(lexar(formula, CONSTANTES))).toBe(formula);
  });

  it("normaliza os espaços", () => {
    expect(paraTexto(lexar("a+b*( c-1 )", CONSTANTES))).toBe("a + b * (c - 1)");
  });

  it("ida e volta não perde nenhum bloco (mesmos tipos e textos)", () => {
    const formulas = [
      "a+b",
      "se( a>=1 ,soma(b,c) , 0 )",
      "-(-a)",
      "a ** -2",
      "1.5*x",
      "a.b + 'x'",
      "((a))",
      "f(,)",
    ];
    for (const formula of formulas) {
      const antes = lexar(formula, CONSTANTES);
      const depois = lexar(paraTexto(antes), CONSTANTES);

      expect([textos(depois), tipos(depois)]).toEqual([textos(antes), tipos(antes)]);
    }
  });
});

describe("edição dos blocos", () => {
  const base = lexar("a + b", CONSTANTES);

  it("insere nos blocos novos na posição pedida", () => {
    const novos = lexar("2 *", CONSTANTES);

    expect(paraTexto(inserirBlocos(base, 2, novos))).toBe("a + 2 * b");
    expect(paraTexto(inserirBlocos(base, 0, novos))).toBe("2 * a + b");
    expect(paraTexto(inserirBlocos(base, 3, novos))).toBe("a + b 2 *");
  });

  it("move um bloco para outra posição", () => {
    expect(paraTexto(moverBloco(base, 0, 2))).toBe("+ b a");
  });

  it("mover para o mesmo lugar não muda nada", () => {
    expect(moverBloco(base, 1, 1)).toEqual(base);
  });

  it("remove um bloco", () => {
    expect(paraTexto(removerBloco(base, 1))).toBe("a b");
  });

  it("índice fora da lista não muda nada", () => {
    expect(removerBloco(base, 9)).toEqual(base);
    expect(moverBloco(base, 9, 0)).toEqual(base);
  });

  it("uma função entra com os parênteses, e o cursor fica entre eles", () => {
    const { blocos, cursor } = blocosDaFuncao("soma");

    expect(paraTexto(blocos)).toBe("soma()");
    expect(cursor).toBe(2);
  });
});

describe("paresDeBlocos", () => {
  it("casa os parênteses por posição do bloco, também os de função", () => {
    const blocos = lexar("a * (b + soma(c))", CONSTANTES);

    // 0 a, 1 *, 2 (, 3 b, 4 +, 5 soma, 6 (, 7 c, 8 ), 9 )
    expect(paresDeBlocos(blocos)).toEqual({
      pares: [
        [6, 8],
        [2, 9],
      ],
      semPar: [],
    });
  });

  it("aponta parêntese sem par", () => {
    expect(paresDeBlocos(lexar("(a + b", CONSTANTES)).semPar).toEqual([0]);
    expect(paresDeBlocos(lexar("a + b)", CONSTANTES)).semPar).toEqual([3]);
  });
});

describe("resolverSolto", () => {
  it("um item da paleta solto sobre um bloco entra antes dele", () => {
    expect(resolverSolto("item-campo-a", "bloco-2", 5)).toEqual({ tipo: "inserir", posicao: 2 });
  });

  it("solto no fim da fórmula, ou sobre o espaço vazio, entra no fim", () => {
    expect(resolverSolto("item-campo-a", "bloco-fim", 5)).toEqual({ tipo: "inserir", posicao: 5 });
  });

  it("um bloco solto sobre outro vai para a posição dele", () => {
    expect(resolverSolto("bloco-0", "bloco-3", 5)).toEqual({ tipo: "mover", de: 0, para: 3 });
  });

  it("um bloco solto no fim vai para o último lugar", () => {
    expect(resolverSolto("bloco-1", "bloco-fim", 5)).toEqual({ tipo: "mover", de: 1, para: 4 });
  });

  it("solto no mesmo lugar, fora de tudo ou sobre algo desconhecido, não muda nada", () => {
    expect(resolverSolto("bloco-2", "bloco-2", 5)).toBeNull();
    expect(resolverSolto("bloco-2", null, 5)).toBeNull();
    expect(resolverSolto("item-x", "outra-coisa", 5)).toBeNull();
    expect(resolverSolto("qualquer", "bloco-1", 5)).toBeNull();
  });
});
