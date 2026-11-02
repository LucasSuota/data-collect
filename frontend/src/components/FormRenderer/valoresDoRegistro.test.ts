import type { Definicao } from "../../api/cliente";
import { calculadosDoRegistro, valoresDoRegistro } from "./valoresDoRegistro";

const DEFINICAO: Definicao = {
  campos: [
    { id: "secao", tipo: "secao", rotulo: "S" },
    { id: "obs", tipo: "texto", rotulo: "Obs" },
    { id: "fck", tipo: "numero", rotulo: "fck" },
    { id: "ok", tipo: "sim_nao", rotulo: "Ok" },
    { id: "local", tipo: "localizacao", rotulo: "Local" },
    { id: "fotos", tipo: "foto", rotulo: "Fotos" },
    { id: "ensaio", tipo: "referencia", rotulo: "Ensaio", formulario: "ensaio" },
    { id: "dobro", tipo: "calculado", rotulo: "Dobro", formula: "fck * 2" },
  ],
};

describe("valoresDoRegistro", () => {
  it("devolve só os campos de entrada, no formato que o formulário edita", () => {
    const dados = {
      obs: "x",
      fck: "25.5",
      ok: false,
      local: { latitude: "-23.5", longitude: "-46.6" },
      fotos: [3, 4],
      ensaio: 12,
      dobro: { valor: "51", erro: null },
    };

    expect(valoresDoRegistro(DEFINICAO, dados)).toEqual({
      obs: "x",
      fck: "25.5",
      ok: false,
      local: { latitude: "-23.5", longitude: "-46.6" },
      fotos: [3, 4],
      ensaio: 12,
    });
  });

  it("campo vazio (null) ou ausente vira undefined, como um formulário novo", () => {
    expect(valoresDoRegistro(DEFINICAO, { obs: null, fck: null })).toEqual({});
  });

  it("ignora valor de tipo inesperado em vez de quebrar", () => {
    expect(valoresDoRegistro(DEFINICAO, { fck: 5, ok: "sim", fotos: "x", local: 3 })).toEqual({});
  });
});

describe("calculadosDoRegistro", () => {
  it("separa o {valor, erro} de cada campo calculado", () => {
    const dados = { fck: "1", dobro: { valor: null, erro: "Divisão por zero." } };

    expect(calculadosDoRegistro(DEFINICAO, dados)).toEqual({
      dobro: { valor: null, erro: "Divisão por zero." },
    });
  });

  it("registro de versão antiga sem o calculado simplesmente não o traz", () => {
    expect(calculadosDoRegistro(DEFINICAO, {})).toEqual({});
  });
});
