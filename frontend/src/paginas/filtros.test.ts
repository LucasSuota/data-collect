import type { ResumoDeFormulario } from "../api/cliente";
import {
  combinaComBusca,
  filtrarArvore,
  listarDaTela,
  normalizar,
  rotuloDoCaminho,
  type OrdemDaLista,
} from "./filtros";
import { montarArvore, type Pasta } from "./pastas";

const pasta = (id: number, nome: string, pasta_pai_id: number | null = null): Pasta => ({
  id,
  nome,
  pasta_pai_id,
  criado_em: "2026-11-02T10:00:00+00:00",
});

const formulario = (
  id: number,
  nome: string,
  pasta_id: number | null = null,
  criado_em = "2026-11-02T10:00:00+00:00",
): ResumoDeFormulario => ({
  id,
  nome,
  criado_em,
  versao_atual_id: id * 10,
  versao_atual_numero: 1,
  pasta_id,
});

const OBRAS = pasta(1, "Obras");
const LAB = pasta(2, "Laboratório");
const FUNDACAO = pasta(3, "Fundação", 1);
const PASTAS = [OBRAS, LAB, FUNDACAO];

const FORMULARIOS = [
  formulario(10, "Densidade", null, "2026-11-01T08:00:00+00:00"),
  formulario(11, "Sondagem", 1, "2026-11-03T08:00:00+00:00"),
  formulario(12, "Estacas SPT", 3, "2026-11-02T08:00:00+00:00"),
  formulario(13, "Ensaio de umidade", 2, "2026-10-30T08:00:00+00:00"),
];

const nomes = (itens: { nome: string }[]) => itens.map((i) => i.nome);

describe("normalizar e combinaComBusca", () => {
  it("ignora acentos, maiúsculas e espaços nas pontas", () => {
    expect(normalizar("  FUNDAÇÃO ")).toBe("fundacao");
  });

  it("busca vazia combina com tudo", () => {
    expect(combinaComBusca("Qualquer coisa", "  ")).toBe(true);
  });

  it("encontra sem digitar os acentos", () => {
    expect(combinaComBusca("Laboratório", "laboratorio")).toBe(true);
  });

  it("exige todas as palavras, em qualquer ordem", () => {
    expect(combinaComBusca("Ensaio de umidade", "umidade ensaio")).toBe(true);
    expect(combinaComBusca("Ensaio de umidade", "umidade proctor")).toBe(false);
  });
});

describe("listarDaTela sem busca", () => {
  const base = { formularios: FORMULARIOS, pastas: PASTAS, termo: "", escopo: "tudo" as const };

  it("na raiz traz as pastas de cima e só os formulários sem pasta", () => {
    const lista = listarDaTela({ ...base, atualId: null, ordem: "nome-asc" });

    expect(nomes(lista.pastas)).toEqual(["Laboratório", "Obras"]);
    expect(nomes(lista.formularios)).toEqual(["Densidade"]);
  });

  it("dentro de uma pasta traz as filhas e os formulários dela", () => {
    const lista = listarDaTela({ ...base, atualId: 1, ordem: "nome-asc" });

    expect(nomes(lista.pastas)).toEqual(["Fundação"]);
    expect(nomes(lista.formularios)).toEqual(["Sondagem"]);
  });
});

describe("listarDaTela com busca", () => {
  const base = { formularios: FORMULARIOS, pastas: PASTAS, ordem: "nome-asc" as const };

  it("procura em todas as pastas, formulários e pastas juntos", () => {
    const lista = listarDaTela({ ...base, atualId: null, termo: "fund", escopo: "tudo" });

    expect(nomes(lista.pastas)).toEqual(["Fundação"]);
    expect(nomes(lista.formularios)).toEqual([]);
  });

  it("acha formulário que está dentro de outra pasta", () => {
    const lista = listarDaTela({ ...base, atualId: 2, termo: "sond", escopo: "tudo" });

    expect(nomes(lista.formularios)).toEqual(["Sondagem"]);
  });

  it("no escopo da pasta, só enxerga a pasta aberta e as descendentes", () => {
    const lista = listarDaTela({ ...base, atualId: 1, termo: "s", escopo: "pasta" });

    expect(nomes(lista.formularios)).toEqual(["Estacas SPT", "Sondagem"]);
    expect(nomes(lista.pastas)).toEqual([]);
  });

  it("no escopo da pasta, a própria pasta aberta não aparece como resultado", () => {
    const lista = listarDaTela({ ...base, atualId: 1, termo: "obras", escopo: "pasta" });

    expect(nomes(lista.pastas)).toEqual([]);
  });

  it("escopo da pasta na raiz equivale a procurar em tudo", () => {
    const lista = listarDaTela({ ...base, atualId: null, termo: "ensaio", escopo: "pasta" });

    expect(nomes(lista.formularios)).toEqual(["Ensaio de umidade"]);
  });
});

describe("listarDaTela: ordem", () => {
  const todos = (ordem: OrdemDaLista) =>
    nomes(
      listarDaTela({
        formularios: FORMULARIOS,
        pastas: PASTAS,
        atualId: null,
        termo: "e",
        escopo: "tudo",
        ordem,
      }).formularios,
    );

  it("por nome, de A a Z e de Z a A", () => {
    expect(todos("nome-asc")).toEqual([
      "Densidade",
      "Ensaio de umidade",
      "Estacas SPT",
      "Sondagem",
    ]);
    expect(todos("nome-desc")).toEqual([
      "Sondagem",
      "Estacas SPT",
      "Ensaio de umidade",
      "Densidade",
    ]);
  });

  it("por data de criação, dos mais recentes aos mais antigos e o inverso", () => {
    expect(todos("recentes")).toEqual([
      "Sondagem",
      "Estacas SPT",
      "Densidade",
      "Ensaio de umidade",
    ]);
    expect(todos("antigos")).toEqual(["Ensaio de umidade", "Densidade", "Estacas SPT", "Sondagem"]);
  });

  it("as pastas seguem o nome mesmo quando a ordem é por data", () => {
    const lista = listarDaTela({
      formularios: [],
      pastas: PASTAS,
      atualId: null,
      termo: "o",
      escopo: "tudo",
      ordem: "recentes",
    });

    expect(nomes(lista.pastas)).toEqual(["Fundação", "Laboratório", "Obras"]);
  });

  it("não altera a lista recebida", () => {
    const copia = [...FORMULARIOS];
    listarDaTela({
      formularios: FORMULARIOS,
      pastas: PASTAS,
      atualId: null,
      termo: "e",
      escopo: "tudo",
      ordem: "nome-desc",
    });

    expect(FORMULARIOS).toEqual(copia);
  });
});

describe("rotuloDoCaminho", () => {
  it("junta os nomes da raiz até a pasta", () => {
    expect(rotuloDoCaminho(PASTAS, 3)).toBe("Obras / Fundação");
  });

  it("sem pasta, diz que está na raiz", () => {
    expect(rotuloDoCaminho(PASTAS, null)).toBe("Sem pasta");
  });
});

describe("filtrarArvore", () => {
  const arvore = montarArvore(PASTAS);

  it("sem busca devolve a árvore inteira", () => {
    expect(filtrarArvore(arvore, "")).toBe(arvore);
  });

  it("mantém o ramo até a pasta encontrada", () => {
    const filtrada = filtrarArvore(arvore, "fundacao");

    expect(filtrada.map((no) => no.pasta.nome)).toEqual(["Obras"]);
    expect(filtrada[0]?.filhos.map((no) => no.pasta.nome)).toEqual(["Fundação"]);
  });

  it("pasta que combina leva todas as filhas, para ver o que há dentro", () => {
    const filtrada = filtrarArvore(arvore, "obras");

    expect(filtrada[0]?.filhos.map((no) => no.pasta.nome)).toEqual(["Fundação"]);
  });

  it("sem nenhuma combinação, a lista fica vazia", () => {
    expect(filtrarArvore(arvore, "zzz")).toEqual([]);
  });
});
