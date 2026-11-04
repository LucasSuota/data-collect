import type { Definicao, ErroDeCampo } from "../api/cliente";
import {
  AREA_DA_LISTA,
  adicionarCampo,
  aplicarArraste,
  atualizarCampo,
  deDefinicao,
  deRascunho,
  mapearErros,
  moverCampo,
  paraDefinicao,
  removerCampo,
  type CampoEmEdicao,
} from "./estado";

let contador = 0;
const gerarChave = () => `k${++contador}`;

function campo(
  parcial: Partial<CampoEmEdicao> & Pick<CampoEmEdicao, "id" | "tipo">,
): CampoEmEdicao {
  return {
    chave: parcial.id,
    rotulo: parcial.id,
    obrigatorio: false,
    unidade: "",
    casasDecimais: "",
    opcoes: "",
    formula: "",
    formulario: "",
    compartilhado: false,
    ...parcial,
  };
}

const ids = (campos: CampoEmEdicao[]) => campos.map((c) => c.id);

describe("adicionar, remover e reordenar", () => {
  beforeEach(() => (contador = 0));

  it("adiciona um campo do tipo escolhido, com id único gerado e rótulo padrão", () => {
    const campos = adicionarCampo([], "numero", "Número", gerarChave);

    expect(campos).toHaveLength(1);
    expect(campos[0]).toMatchObject({
      tipo: "numero",
      id: "numero_1",
      rotulo: "Número",
      chave: "k1",
    });
  });

  it("não repete o id de um campo existente", () => {
    let campos = adicionarCampo([], "texto", "Texto", gerarChave);
    campos = adicionarCampo(campos, "texto", "Texto", gerarChave);
    campos = adicionarCampo(campos, "texto", "Texto", gerarChave);

    expect(ids(campos)).toEqual(["texto_1", "texto_2", "texto_3"]);
  });

  it("reaproveita o número livre quando um campo some do meio", () => {
    let campos = [campo({ id: "texto_1", tipo: "texto" }), campo({ id: "texto_3", tipo: "texto" })];
    campos = adicionarCampo(campos, "texto", "Texto", gerarChave);

    expect(ids(campos)).toEqual(["texto_1", "texto_3", "texto_2"]);
  });

  it("adiciona numa posição (drop sobre outro campo)", () => {
    const base = [campo({ id: "a", tipo: "texto" }), campo({ id: "b", tipo: "texto" })];

    expect(ids(adicionarCampo(base, "data", "Data", gerarChave, 1))).toEqual(["a", "data_1", "b"]);
    expect(ids(adicionarCampo(base, "data", "Data", gerarChave, 0))).toEqual(["data_1", "a", "b"]);
    expect(ids(adicionarCampo(base, "data", "Data", gerarChave, 99))).toEqual(["a", "b", "data_1"]);
  });

  it("não altera a lista original", () => {
    const base = [campo({ id: "a", tipo: "texto" })];

    adicionarCampo(base, "texto", "Texto", gerarChave);
    removerCampo(base, "a");
    moverCampo(base, "a", 0);

    expect(ids(base)).toEqual(["a"]);
  });

  it("remove pelo identificador estável, não pela posição", () => {
    const base = [campo({ id: "a", tipo: "texto" }), campo({ id: "b", tipo: "texto" })];

    expect(ids(removerCampo(base, "b"))).toEqual(["a"]);
  });

  it("move um campo para outra posição", () => {
    const base = ["a", "b", "c"].map((id) => campo({ id, tipo: "texto" }));

    expect(ids(moverCampo(base, "a", 2))).toEqual(["b", "c", "a"]);
    expect(ids(moverCampo(base, "c", 0))).toEqual(["c", "a", "b"]);
    expect(ids(moverCampo(base, "b", 1))).toEqual(["a", "b", "c"]);
  });

  it("move com chave inexistente ou posição fora do limite sem quebrar", () => {
    const base = ["a", "b"].map((id) => campo({ id, tipo: "texto" }));

    expect(ids(moverCampo(base, "fantasma", 0))).toEqual(["a", "b"]);
    expect(ids(moverCampo(base, "a", 50))).toEqual(["b", "a"]);
    expect(ids(moverCampo(base, "a", -3))).toEqual(["a", "b"]);
  });

  it("atualiza só o campo da chave dada", () => {
    const base = [campo({ id: "a", tipo: "texto" }), campo({ id: "b", tipo: "texto" })];

    const novo = atualizarCampo(base, "b", { rotulo: "Novo rótulo", obrigatorio: true });

    expect(novo[1]).toMatchObject({ rotulo: "Novo rótulo", obrigatorio: true });
    expect(novo[0]).toBe(base[0]);
  });
});

describe("paraDefinicao", () => {
  it("monta a definição do contrato só com o que foi preenchido", () => {
    const definicao = paraDefinicao([
      campo({
        id: "fck",
        tipo: "numero",
        rotulo: "fck",
        unidade: "MPa",
        obrigatorio: true,
        casasDecimais: "1",
      }),
      campo({ id: "obs", tipo: "texto", rotulo: "Obs" }),
    ]);

    expect(definicao).toEqual({
      campos: [
        {
          id: "fck",
          tipo: "numero",
          rotulo: "fck",
          obrigatorio: true,
          unidade: "MPa",
          casas_decimais: 1,
        },
        { id: "obs", tipo: "texto", rotulo: "Obs" },
      ],
    });
  });

  it("opções: uma por linha, sem linhas vazias nem espaços nas pontas", () => {
    const definicao = paraDefinicao([
      campo({ id: "r", tipo: "selecao", opcoes: " Aprovado \n\nReprovado\n  " }),
    ]);

    expect(definicao.campos[0]).toMatchObject({ opcoes: ["Aprovado", "Reprovado"] });
  });

  it("fórmula, formulário de origem e compartilhado", () => {
    const definicao = paraDefinicao([
      campo({ id: "e", tipo: "referencia", formulario: "ensaio" }),
      campo({ id: "c", tipo: "calculado", formula: "a * 2", compartilhado: true }),
    ]);

    expect(definicao.campos).toEqual([
      { id: "e", tipo: "referencia", rotulo: "e", formulario: "ensaio" },
      { id: "c", tipo: "calculado", rotulo: "c", formula: "a * 2", compartilhado: true },
    ]);
  });

  it("número inválido segue como texto, para o servidor reclamar no campo certo", () => {
    const definicao = paraDefinicao([campo({ id: "n", tipo: "numero", casasDecimais: "uma" })]);

    expect(definicao.campos[0]).toMatchObject({ casas_decimais: "uma" });
  });

  it("só envia as propriedades que o catálogo diz que o tipo aceita", () => {
    const aceitas = { texto: ["obrigatorio"], numero: ["obrigatorio", "unidade"] };
    const definicao = paraDefinicao(
      [
        // era número, virou texto: a unidade que sobrou no estado não pode ir (o servidor recusaria)
        campo({ id: "a", tipo: "texto", unidade: "kg", obrigatorio: true }),
        campo({ id: "b", tipo: "numero", unidade: "kg" }),
      ],
      aceitas,
    );

    expect(definicao.campos).toEqual([
      { id: "a", tipo: "texto", rotulo: "a", obrigatorio: true },
      { id: "b", tipo: "numero", rotulo: "b", unidade: "kg" },
    ]);
  });
});

describe("deDefinicao", () => {
  beforeEach(() => (contador = 0));

  it("carrega uma definição existente para edição e volta igual", () => {
    const original: Definicao = {
      campos: [
        {
          id: "fck",
          tipo: "numero",
          rotulo: "fck",
          unidade: "MPa",
          obrigatorio: true,
          casas_decimais: 1,
        },
        { id: "r", tipo: "selecao", rotulo: "R", opcoes: ["A", "B"] },
        { id: "c", tipo: "calculado", rotulo: "C", formula: "fck * 2", compartilhado: true },
        { id: "e", tipo: "referencia", rotulo: "E", formulario: "ensaio" },
      ],
    };

    const campos = deDefinicao(original, gerarChave);

    expect(campos.map((c) => c.chave)).toEqual(["k1", "k2", "k3", "k4"]);
    expect(campos[1]).toMatchObject({ opcoes: "A\nB" });
    expect(campos[0]).toMatchObject({ casasDecimais: "1", unidade: "MPa", obrigatorio: true });
    expect(paraDefinicao(campos)).toEqual(original);
  });
});

describe("mapearErros", () => {
  const instantaneo = [
    { chave: "k1", id: "fck" },
    { chave: "k2", id: "res" },
    { chave: "k3", id: "res" }, // id duplicado
  ];
  const erro = (
    campoDoErro: string,
    mensagem = "m",
    posicao?: ErroDeCampo["posicao"],
  ): ErroDeCampo => ({
    campo: campoDoErro,
    mensagem,
    posicao,
  });

  it("erro por id de campo vai para o campo, com a propriedade", () => {
    const { porCampo, globais } = mapearErros(
      [erro("fck.casas_decimais", "negativo")],
      instantaneo,
    );

    expect(porCampo).toEqual({
      k1: [{ propriedade: "casas_decimais", mensagem: "negativo", posicao: undefined }],
    });
    expect(globais).toEqual([]);
  });

  it("erro de fórmula leva a posição para o editor sublinhar", () => {
    const { porCampo } = mapearErros(
      [erro("fck.formula", "ruim", { inicio: 2, fim: 7 })],
      instantaneo,
    );

    expect(porCampo["k1"]?.[0]).toMatchObject({
      propriedade: "formula",
      posicao: { inicio: 2, fim: 7 },
    });
  });

  it("erro no próprio id usa o índice do instantâneo enviado", () => {
    const { porCampo } = mapearErros([erro("campos[2].id", "duplicado")], instantaneo);

    expect(porCampo).toEqual({
      k3: [{ propriedade: "id", mensagem: "duplicado", posicao: undefined }],
    });
  });

  it("o erro continua no campo certo mesmo se o usuário reordenar depois (a chave é estável)", () => {
    const { porCampo } = mapearErros([erro("campos[0].id", "reservado")], instantaneo);
    const reordenado = [
      campo({ id: "res", tipo: "texto", chave: "k2" }),
      campo({ id: "fck", tipo: "texto", chave: "k1" }),
    ];

    // o erro ficou com "k1"; na tela nova, k1 está na segunda posição, e é ele que mostra o erro
    expect(Object.keys(porCampo)).toEqual(["k1"]);
    expect(reordenado.findIndex((c) => porCampo[c.chave])).toBe(1);
  });

  it("erro global (sem a lista campos) e erro que não casa com nenhum campo viram globais", () => {
    const { porCampo, globais } = mapearErros(
      [
        erro("campos", "A definição precisa ter a lista 'campos'."),
        erro("fantasma.tipo", "x"),
        erro("campos[9].id", "y"),
      ],
      instantaneo,
    );

    expect(porCampo).toEqual({});
    expect(globais).toEqual([
      "A definição precisa ter a lista 'campos'.",
      "fantasma.tipo: x",
      "campos[9].id: y",
    ]);
  });

  it("erro sem propriedade (campo removido de um contrato) fica no campo, propriedade vazia", () => {
    const { porCampo } = mapearErros([erro("fck", "não pode ser removido")], instantaneo);

    expect(porCampo["k1"]).toEqual([
      { propriedade: "", mensagem: "não pode ser removido", posicao: undefined },
    ]);
  });

  it("vários erros no mesmo campo", () => {
    const { porCampo } = mapearErros([erro("fck.tipo", "a"), erro("fck.rotulo", "b")], instantaneo);

    expect(porCampo["k1"]).toHaveLength(2);
  });
});

describe("aplicarArraste", () => {
  beforeEach(() => (contador = 0));
  const base = () => ["a", "b", "c"].map((id) => campo({ id, tipo: "texto" }));
  const rotulos = { numero: "Número", data: "Data" };

  it("soltar um tipo da paleta sobre um campo insere antes dele", () => {
    const novo = aplicarArraste(
      base(),
      { origem: "paleta", tipo: "numero" },
      "b",
      rotulos,
      gerarChave,
    );

    expect(ids(novo)).toEqual(["a", "numero_1", "b", "c"]);
  });

  it("soltar um tipo da paleta na área vazia da lista acrescenta no fim", () => {
    const novo = aplicarArraste(
      base(),
      { origem: "paleta", tipo: "data" },
      AREA_DA_LISTA,
      rotulos,
      gerarChave,
    );

    expect(ids(novo)).toEqual(["a", "b", "c", "data_1"]);
  });

  it("soltar fora de qualquer área não faz nada", () => {
    const campos = base();

    expect(
      aplicarArraste(campos, { origem: "paleta", tipo: "data" }, null, rotulos, gerarChave),
    ).toBe(campos);
    expect(aplicarArraste(campos, { origem: "campo", chave: "a" }, null, rotulos, gerarChave)).toBe(
      campos,
    );
  });

  it("arrastar um campo sobre outro move para a posição do alvo (para baixo e para cima)", () => {
    expect(
      ids(aplicarArraste(base(), { origem: "campo", chave: "a" }, "c", rotulos, gerarChave)),
    ).toEqual(["b", "c", "a"]);
    expect(
      ids(aplicarArraste(base(), { origem: "campo", chave: "c" }, "a", rotulos, gerarChave)),
    ).toEqual(["c", "a", "b"]);
  });

  it("soltar um campo sobre si mesmo não muda a ordem", () => {
    const campos = base();

    expect(
      ids(aplicarArraste(campos, { origem: "campo", chave: "b" }, "b", rotulos, gerarChave)),
    ).toEqual(["a", "b", "c"]);
  });

  it("soltar um campo na área da lista manda para o fim", () => {
    const novo = aplicarArraste(
      base(),
      { origem: "campo", chave: "a" },
      AREA_DA_LISTA,
      rotulos,
      gerarChave,
    );

    expect(ids(novo)).toEqual(["b", "c", "a"]);
  });

  it("tipo sem rótulo no catálogo usa o próprio nome do tipo", () => {
    const novo = aplicarArraste(
      [],
      { origem: "paleta", tipo: "localizacao" },
      AREA_DA_LISTA,
      rotulos,
      gerarChave,
    );

    expect(novo[0]).toMatchObject({ tipo: "localizacao", rotulo: "localizacao" });
  });
});

describe("deRascunho", () => {
  it("lê uma definição proposta pela IA, mesmo com tipo que o catálogo não conhece", () => {
    const campos = deRascunho(
      {
        campos: [
          { id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%", casas_decimais: 2 },
          { id: "classe", tipo: "moeda", rotulo: "Classe", opcoes: ["A", "B"], obrigatorio: true },
          {
            id: "ok",
            tipo: "calculado",
            rotulo: "OK",
            formula: "umidade > 3",
            compartilhado: true,
          },
        ],
      },
      gerarChave,
    );

    expect(campos.map((c) => [c.id, c.tipo, c.unidade, c.casasDecimais])).toEqual([
      ["umidade", "numero", "%", "2"],
      ["classe", "moeda", "", ""],
      ["ok", "calculado", "", ""],
    ]);
    expect(campos[1]).toMatchObject({ opcoes: "A\nB", obrigatorio: true });
    expect(campos[2]).toMatchObject({ formula: "umidade > 3", compartilhado: true });
    expect(new Set(campos.map((c) => c.chave)).size).toBe(3);
  });

  it("tolera lixo sem perder a posição dos campos (o índice dos erros precisa continuar valendo)", () => {
    const campos = deRascunho(
      { campos: ["texto solto", null, { id: 3, tipo: ["x"], rotulo: null }, { id: "a" }] },
      gerarChave,
    );

    expect(campos).toHaveLength(4);
    expect(campos.map((c) => c.id)).toEqual(["", "", "", "a"]);
    expect(campos.every((c) => typeof c.tipo === "string" && typeof c.rotulo === "string")).toBe(
      true,
    );
  });

  it.each([null, undefined, 5, "x", {}, { campos: "não é lista" }])(
    "definição sem lista de campos (%j) vira lista vazia",
    (definicao) => {
      expect(deRascunho(definicao, gerarChave)).toEqual([]);
    },
  );

  it("volta igual para a definição do contrato (ida e volta)", () => {
    const original = {
      campos: [
        { id: "umidade", tipo: "numero", rotulo: "Umidade", unidade: "%", obrigatorio: true },
        { id: "ok", tipo: "calculado", rotulo: "OK", formula: "umidade > 3" },
      ],
    };

    expect(paraDefinicao(deRascunho(original, gerarChave))).toEqual(original);
  });
});
