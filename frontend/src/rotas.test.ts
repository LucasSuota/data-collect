import { caminhoDe, lerRota, type Rota } from "./rotas";

const CASOS: [string, Rota][] = [
  ["#/", { nome: "formularios" }],
  ["#/formularios/3/registros", { nome: "registros", formularioId: 3 }],
  ["#/formularios/3/novo", { nome: "novoRegistro", formularioId: 3 }],
  ["#/registros/9", { nome: "registro", registroId: 9 }],
  ["#/construtor", { nome: "novoFormulario" }],
  ["#/formularios/3/editar", { nome: "editarFormulario", formularioId: 3 }],
];

describe("rotas", () => {
  it.each(CASOS)("%s ⇄ %j", (hash, rota) => {
    expect(lerRota(hash)).toEqual(rota);
    expect(caminhoDe(rota)).toBe(hash);
  });

  it.each(["", "#", "#/"])("a raiz (%j) é a lista de formulários", (hash) => {
    expect(lerRota(hash)).toEqual({ nome: "formularios" });
  });

  it.each([
    "#/nada",
    "#/formularios/abc/registros",
    "#/registros/-1",
    "#/formularios//novo",
    "#/registros/1/x",
  ])("%s não existe", (hash) => {
    expect(lerRota(hash)).toEqual({ nome: "naoEncontrada" });
  });
});
