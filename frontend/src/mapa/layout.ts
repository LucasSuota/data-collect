import type { Grafo, NoDoGrafo } from "./grafo";

export interface Medidas {
  largura: number;
  altura: (no: NoDoGrafo) => number;
  folgaX: number;
  folgaY: number;
}

export interface Posicao {
  x: number;
  y: number;
}

export interface Organizacao {
  posicoes: Map<string, Posicao>;
  largura: number;
  altura: number;
}

/**
 * Layout em camadas, da origem (esquerda) para os dependentes (direita), como num fluxo do n8n.
 * A coluna de cada nó é o caminho mais longo até ele (a mesma ordem da cascata de recálculo);
 * dentro da coluna, a ordem segue a média das posições dos vizinhos para as linhas cruzarem menos.
 */
export function organizar(grafo: Grafo, medidas: Medidas): Organizacao {
  const ids = grafo.nos.map((no) => no.id);
  const camadaDe = camadas(ids, grafo);
  const colunas: NoDoGrafo[][] = [];
  for (const no of grafo.nos) (colunas[camadaDe.get(no.id) ?? 0] ??= []).push(no);
  const preenchidas = colunas.filter((coluna) => coluna !== undefined);

  const ordem = new Map<string, number>();
  const reindexar = () =>
    preenchidas.forEach((coluna) => coluna.forEach((no, indice) => ordem.set(no.id, indice)));
  reindexar();

  const vizinhos = (id: string, sentido: "origem" | "destino") =>
    grafo.arestas
      .filter((a) => (sentido === "origem" ? a.para === id : a.de === id))
      .map((a) => ordem.get(sentido === "origem" ? a.de : a.para) ?? 0);
  const media = (valores: number[], padrao: number) =>
    valores.length === 0 ? padrao : valores.reduce((soma, v) => soma + v, 0) / valores.length;

  // Duas passadas (para a frente e para trás) bastam para grafos pequenos como estes.
  for (const passada of ["origem", "destino"] as const) {
    const colunasNaOrdem = passada === "origem" ? preenchidas : [...preenchidas].reverse();
    for (const coluna of colunasNaOrdem) {
      const chave = new Map(
        coluna.map((no) => [no.id, media(vizinhos(no.id, passada), ordem.get(no.id) ?? 0)]),
      );
      coluna.sort((a, b) => (chave.get(a.id) ?? 0) - (chave.get(b.id) ?? 0));
      coluna.forEach((no, indice) => ordem.set(no.id, indice));
    }
  }

  const alturaDaColuna = (coluna: NoDoGrafo[]) =>
    coluna.reduce((soma, no) => soma + medidas.altura(no), 0) +
    medidas.folgaY * Math.max(0, coluna.length - 1);
  const maisAlta = Math.max(0, ...preenchidas.map(alturaDaColuna));

  const posicoes = new Map<string, Posicao>();
  preenchidas.forEach((coluna, indiceDaColuna) => {
    let y = (maisAlta - alturaDaColuna(coluna)) / 2;
    for (const no of coluna) {
      posicoes.set(no.id, { x: indiceDaColuna * (medidas.largura + medidas.folgaX), y });
      y += medidas.altura(no) + medidas.folgaY;
    }
  });

  return {
    posicoes,
    largura:
      preenchidas.length === 0
        ? 0
        : preenchidas.length * medidas.largura + (preenchidas.length - 1) * medidas.folgaX,
    altura: maisAlta,
  };
}

/** Caminho mais longo até cada nó; o limite de passos impede laço infinito num ciclo. */
function camadas(ids: string[], grafo: Grafo): Map<string, number> {
  const camada = new Map(ids.map((id) => [id, 0]));
  for (let passo = 0; passo < ids.length; passo++) {
    let mudou = false;
    for (const aresta of grafo.arestas) {
      const de = camada.get(aresta.de);
      const para = camada.get(aresta.para);
      if (de === undefined || para === undefined || para > de) continue;
      camada.set(aresta.para, de + 1);
      mudou = true;
    }
    if (!mudou) break;
  }
  // Compacta: com ciclo, a numeração pode ter saltos; as colunas vazias são descartadas acima.
  return camada;
}
