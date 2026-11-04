import { caminhoDe, lerRota, type Rota } from "./rotas";

const CASOS: [string, Rota][] = [
  ["#/", { nome: "inicio" }],
  ["#/formularios", { nome: "formularios" }],
  ["#/registros", { nome: "registrosRecentes" }],
  ["#/equipe", { nome: "equipe" }],
  ["#/cargos", { nome: "cargos" }],
  ["#/ia", { nome: "ia" }],
  ["#/chat", { nome: "chat" }],
  ["#/perfil", { nome: "perfil" }],
  ["#/exemplos", { nome: "exemplos" }],
  ["#/termos", { nome: "termos" }],
  ["#/privacidade", { nome: "privacidade" }],
  ["#/ajuda", { nome: "ajuda" }],
  ["#/ajuda/primeiros-passos", { nome: "ajuda", guia: "primeiros-passos" }],
  ["#/busca/corpo%20de%20prova", { nome: "busca", termo: "corpo de prova" }],
  ["#/convite/abc-123_XYZ", { nome: "convite", token: "abc-123_XYZ" }],
  ["#/formularios/3/registros", { nome: "registros", formularioId: 3 }],
  ["#/formularios/3/novo", { nome: "novoRegistro", formularioId: 3 }],
  ["#/registros/9", { nome: "registro", registroId: 9 }],
  ["#/construtor", { nome: "novoFormulario" }],
  ["#/construtor/ia", { nome: "criarComIa" }],
  ["#/formularios/3/editar", { nome: "editarFormulario", formularioId: 3 }],
  ["#/mapa", { nome: "mapa" }],
  ["#/pastas/5", { nome: "pasta", pastaId: 5 }],
  ["#/construtor/pasta/5", { nome: "novoFormulario", pastaId: 5 }],
];

describe("rotas", () => {
  it.each(CASOS)("%s ⇄ %j", (hash, rota) => {
    expect(lerRota(hash)).toEqual(rota);
    expect(caminhoDe(rota)).toBe(hash);
  });

  it.each(["", "#", "#/"])("a raiz (%j) é o início", (hash) => {
    expect(lerRota(hash)).toEqual({ nome: "inicio" });
  });

  it("um `%` solto na busca é rota inválida, não erro", () => {
    expect(lerRota("#/busca/100%")).toEqual({ nome: "naoEncontrada" });
  });

  it.each([
    "#/nada",
    "#/formularios/abc/registros",
    "#/registros/-1",
    "#/formularios//novo",
    "#/registros/1/x",
    "#/construtor/outra",
    "#/construtor/ia/x",
    "#/mapa/x",
    "#/pastas",
    "#/pastas/0",
    "#/pastas/abc",
    "#/pastas/5/x",
    "#/construtor/pasta",
    "#/construtor/pasta/abc",
  ])("%s não existe", (hash) => {
    expect(lerRota(hash)).toEqual({ nome: "naoEncontrada" });
  });
});
