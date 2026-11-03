import { anunciosDoConstrutor, chaveDoCampoNovo, posicaoDoDestino } from "./arraste";
import { AREA_DA_LISTA, type Arrastado, type CampoEmEdicao } from "./estado";

function campo(chave: string, rotulo: string): CampoEmEdicao {
  return {
    chave,
    id: chave,
    tipo: "texto",
    rotulo,
    obrigatorio: false,
    unidade: "",
    casasDecimais: "",
    opcoes: "",
    formula: "",
    formulario: "",
    compartilhado: false,
    maximo: "",
  };
}

const CAMPOS = [campo("a", "Diâmetro"), campo("b", "Carga"), campo("c", "Resistência")];

describe("posicaoDoDestino", () => {
  it("sobre um campo, é a posição dele (o item novo entra antes)", () => {
    expect(posicaoDoDestino(CAMPOS, "b")).toBe(1);
  });

  it("sobre a área da lista, é o fim", () => {
    expect(posicaoDoDestino(CAMPOS, AREA_DA_LISTA)).toBe(3);
  });

  it("fora de tudo, ou sobre algo desconhecido, não há destino", () => {
    expect(posicaoDoDestino(CAMPOS, null)).toBeNull();
    expect(posicaoDoDestino(CAMPOS, "nada")).toBeNull();
  });
});

describe("chaveDoCampoNovo", () => {
  it("acha o campo que não existia antes", () => {
    const depois = [CAMPOS[0]!, campo("novo", "Novo"), CAMPOS[1]!, CAMPOS[2]!];

    expect(chaveDoCampoNovo(CAMPOS, depois)).toBe("novo");
  });

  it("sem campo novo (uma reordenação), devolve null", () => {
    expect(chaveDoCampoNovo(CAMPOS, [CAMPOS[1]!, CAMPOS[0]!, CAMPOS[2]!])).toBeNull();
  });
});

describe("anunciosDoConstrutor", () => {
  const anuncios = anunciosDoConstrutor({
    campos: () => CAMPOS,
    rotuloDoTipo: (tipo) => (tipo === "numero" ? "Número" : tipo),
  });
  const doCampo = (chave: string): { id: string; data: { current: Arrastado } } => ({
    id: chave,
    data: { current: { origem: "campo", chave } },
  });
  const daPaleta = {
    id: "paleta-numero",
    data: { current: { origem: "paleta", tipo: "numero" } as const },
  };

  it("anuncia o que foi pego", () => {
    expect(anuncios.onDragStart({ active: doCampo("a") })).toBe("Você pegou o campo Diâmetro.");
    expect(anuncios.onDragStart({ active: daPaleta })).toBe(
      "Você pegou o tipo Número. Solte na lista para adicionar um campo.",
    );
  });

  it("anuncia sobre o quê o item está, com a posição", () => {
    expect(anuncios.onDragOver({ active: daPaleta, over: { id: "b" } })).toBe(
      "Sobre o campo Carga, posição 2 de 3.",
    );
    expect(anuncios.onDragOver({ active: daPaleta, over: { id: AREA_DA_LISTA } })).toBe(
      "No fim da lista.",
    );
    expect(anuncios.onDragOver({ active: daPaleta, over: null })).toBe("Fora da lista.");
  });

  it("anuncia a adição de um tipo da paleta na posição em que entrou", () => {
    expect(anuncios.onDragEnd({ active: daPaleta, over: { id: "b" } })).toBe(
      "Campo Número adicionado na posição 2.",
    );
    expect(anuncios.onDragEnd({ active: daPaleta, over: { id: AREA_DA_LISTA } })).toBe(
      "Campo Número adicionado na posição 4.",
    );
  });

  it("anuncia a nova posição de um campo reordenado", () => {
    expect(anuncios.onDragEnd({ active: doCampo("a"), over: { id: "c" } })).toBe(
      "O campo Diâmetro foi movido para a posição 3.",
    );
    expect(anuncios.onDragEnd({ active: doCampo("a"), over: { id: AREA_DA_LISTA } })).toBe(
      "O campo Diâmetro foi movido para a posição 3.",
    );
  });

  it("soltar fora da lista não muda nada, e o cancelamento é anunciado", () => {
    expect(anuncios.onDragEnd({ active: doCampo("a"), over: null })).toBe(
      "Solto fora da lista. Nada mudou.",
    );
    expect(anuncios.onDragCancel({ active: doCampo("a") })).toBe("Movimento cancelado.");
  });

  it("um item de outro tipo de arraste não gera anúncio", () => {
    expect(anuncios.onDragStart({ active: { id: "x", data: {} } })).toBeUndefined();
  });
});
