import { formatarNumero } from "./numero";

describe("formatarNumero", () => {
  it("troca o ponto por vírgula, como no CSV em português", () => {
    expect(formatarNumero("25.5", null)).toBe("25,5");
  });

  it("sem casas_decimais mostra o valor completo", () => {
    expect(formatarNumero("25.46479089470325", null)).toBe("25,46479089470325");
    expect(formatarNumero("25.50", null)).toBe("25,50");
  });

  it("arredonda para o número de casas pedido", () => {
    expect(formatarNumero("25.46479", 1)).toBe("25,5");
    expect(formatarNumero("25.44", 1)).toBe("25,4");
    expect(formatarNumero("25.46479", 2)).toBe("25,46");
  });

  it("completa com zeros quando faltam casas", () => {
    expect(formatarNumero("25", 1)).toBe("25,0");
    expect(formatarNumero("25.5", 3)).toBe("25,500");
  });

  it("zero casas decimais não deixa vírgula", () => {
    expect(formatarNumero("25.5", 0)).toBe("26");
    expect(formatarNumero("25.4", 0)).toBe("25");
  });

  it("arredonda o meio para cima, igual ao CSV do backend (e ao contrário do toFixed)", () => {
    expect(formatarNumero("0.25", 1)).toBe("0,3");
    expect(formatarNumero("0.35", 1)).toBe("0,4"); // (0.35).toFixed(1) dá "0.3"
    expect(formatarNumero("1.005", 2)).toBe("1,01"); // (1.005).toFixed(2) dá "1.00"
    expect(formatarNumero("2.5", 0)).toBe("3");
  });

  it("negativos arredondam o meio para longe do zero", () => {
    expect(formatarNumero("-0.25", 1)).toBe("-0,3");
    expect(formatarNumero("-3.5", 1)).toBe("-3,5");
  });

  it("zero negativo depois de arredondar sai sem sinal", () => {
    expect(formatarNumero("-0.04", 1)).toBe("0,0");
  });

  it("propaga o vai-um por vários dígitos", () => {
    expect(formatarNumero("9.995", 2)).toBe("10,00");
    expect(formatarNumero("99.9", 0)).toBe("100");
  });

  it("não perde precisão em números grandes", () => {
    expect(formatarNumero("1234567890123456789012345.5", 10)).toBe(
      "1234567890123456789012345,5000000000",
    );
  });

  it("aceita sinal explícito e notação sem parte inteira", () => {
    expect(formatarNumero("+7", 1)).toBe("7,0");
    expect(formatarNumero(".5", 1)).toBe("0,5");
  });

  it("devolve o texto como veio quando não é um número", () => {
    expect(formatarNumero("abc", 1)).toBe("abc");
    expect(formatarNumero("", 1)).toBe("");
  });
});
