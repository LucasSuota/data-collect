import { describe, expect, it } from "vitest";
import { adicionarReferencia, idDaReferencia } from "./vinculo";

describe("idDaReferencia", () => {
  it("tira acento e símbolos do nome do formulário", () => {
    expect(idDaReferencia("Ensaio de Compressão", new Set())).toBe("ensaio_de_compressao");
  });

  it("nunca gera `__`, reservado aos campos compartilhados", () => {
    expect(idDaReferencia("A -- B", new Set())).not.toContain("__");
  });

  it("evita nome reservado de fórmula", () => {
    expect(idDaReferencia("Max", new Set())).toBe("max_ref");
  });

  it("começa por letra quando o nome começa por número", () => {
    expect(idDaReferencia("2024 Ensaios", new Set())).toBe("ref_2024_ensaios");
  });

  it("acrescenta sufixo quando o id já existe", () => {
    expect(idDaReferencia("Ensaio", new Set(["ensaio", "ensaio_2"]))).toBe("ensaio_3");
  });

  it("cai num id padrão quando o nome só tem símbolos", () => {
    expect(idDaReferencia("***", new Set())).toBe("origem");
  });
});

describe("adicionarReferencia", () => {
  const definicao = { campos: [{ id: "fck", tipo: "numero", rotulo: "fck" }] };

  it("acrescenta o campo `referencia` apontando pelo NOME da origem", () => {
    const { definicao: nova, campoId, jaExistia } = adicionarReferencia(definicao, "Ensaio");

    expect(jaExistia).toBe(false);
    expect(campoId).toBe("ensaio");
    expect(nova.campos.at(-1)).toEqual({
      id: "ensaio",
      tipo: "referencia",
      rotulo: "Ensaio",
      formulario: "Ensaio",
      obrigatorio: false,
    });
  });

  it("não altera a definição de partida (versões publicadas são imutáveis)", () => {
    adicionarReferencia(definicao, "Ensaio");

    expect(definicao.campos).toHaveLength(1);
  });

  it("não duplica o vínculo que já existe, sem diferenciar maiúsculas", () => {
    const comRef = { campos: [{ id: "e", tipo: "referencia", formulario: "ensaio", rotulo: "E" }] };

    const resultado = adicionarReferencia(comRef, "Ensaio");

    expect(resultado.jaExistia).toBe(true);
    expect(resultado.definicao.campos).toHaveLength(1);
    expect(resultado.campoId).toBe("e");
  });

  it("aceita rascunho sem campos", () => {
    expect(adicionarReferencia({}, "Ensaio").definicao.campos).toHaveLength(1);
  });
});
