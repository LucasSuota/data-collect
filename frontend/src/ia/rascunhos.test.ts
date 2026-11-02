import type { ErroDeCampo } from "../api/cliente";
import { atribuirErrosDoLote, deGerados, type Rascunho } from "./rascunhos";

let contador = 0;
const gerarChave = () => `r${++contador}`;

function rascunho(nome: string, erros: ErroDeCampo[] = []): Rascunho {
  return { chave: nome, nome, definicao: { campos: [] }, erros };
}

describe("deGerados", () => {
  it("dá uma chave estável a cada rascunho e guarda a definição como veio", () => {
    const definicao = { campos: [{ id: "x", tipo: "moeda" }] };

    const rascunhos = deGerados(
      [
        { nome: "Ensaio", definicao, erros: [{ campo: "x.tipo", mensagem: "Tipo desconhecido." }] },
        { nome: "Proctor", definicao: { campos: [] }, erros: [] },
      ],
      gerarChave,
    );

    expect(rascunhos.map((r) => r.nome)).toEqual(["Ensaio", "Proctor"]);
    expect(new Set(rascunhos.map((r) => r.chave)).size).toBe(2);
    expect(rascunhos[0]?.definicao).toBe(definicao);
    expect(rascunhos[0]?.erros).toEqual([{ campo: "x.tipo", mensagem: "Tipo desconhecido." }]);
  });
});

describe("atribuirErrosDoLote", () => {
  it("tira o nome do formulário do início e entrega o erro ao rascunho certo", () => {
    const { rascunhos, globais } = atribuirErrosDoLote(
      [rascunho("Ensaio"), rascunho("Proctor")],
      [{ campo: "Proctor.umidade.formula", mensagem: "Campo desconhecido." }],
    );

    expect(rascunhos[0]?.erros).toEqual([]);
    expect(rascunhos[1]?.erros).toEqual([
      { campo: "umidade.formula", mensagem: "Campo desconhecido." },
    ]);
    expect(globais).toEqual([]);
  });

  it("com nomes que contêm ponto, vale o nome mais longo que casa", () => {
    const { rascunhos } = atribuirErrosDoLote(
      [rascunho("Ensaio"), rascunho("Ensaio.v2")],
      [{ campo: "Ensaio.v2.x.formula", mensagem: "Ruim." }],
    );

    expect(rascunhos[0]?.erros).toEqual([]);
    expect(rascunhos[1]?.erros).toEqual([{ campo: "x.formula", mensagem: "Ruim." }]);
  });

  it("nome repetido: o erro de nome aparece em todos os rascunhos com esse nome", () => {
    const { rascunhos } = atribuirErrosDoLote(
      [rascunho("Ensaio"), rascunho("Ensaio")],
      [{ campo: "Ensaio.nome", mensagem: "Nome repetido no lote." }],
    );

    expect(rascunhos.map((r) => r.erros)).toEqual([
      [{ campo: "nome", mensagem: "Nome repetido no lote." }],
      [{ campo: "nome", mensagem: "Nome repetido no lote." }],
    ]);
  });

  it("erro que não casa com nenhum rascunho vira mensagem global", () => {
    const { rascunhos, globais } = atribuirErrosDoLote(
      [rascunho("Ensaio")],
      [{ campo: "Outro.x", mensagem: "Falhou." }],
    );

    expect(rascunhos[0]?.erros).toEqual([]);
    expect(globais).toEqual(["Outro.x: Falhou."]);
  });

  it("troca os erros antigos pelos novos (não acumula)", () => {
    const antigo = rascunho("Ensaio", [{ campo: "a", mensagem: "velho" }]);

    const { rascunhos } = atribuirErrosDoLote([antigo], []);

    expect(rascunhos[0]?.erros).toEqual([]);
  });
});
