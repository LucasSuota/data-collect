import type { Grafo, NoDoGrafo } from "./grafo";

/**
 * A alternativa ao mapa para telas estreitas e para quem navega por toque ou teclado (AGENTS.md
 * §2.17): a mesma cadeia, como lista indentada da origem para os dependentes.
 */
export function ListaDoMapa({
  grafo,
  aoAbrir,
}: {
  grafo: Grafo;
  aoAbrir: (no: NoDoGrafo) => void;
}) {
  const porId = new Map(grafo.nos.map((n) => [n.id, n]));
  const dependentesDe = (id: string) =>
    grafo.arestas
      .filter((a) => a.de === id)
      .map((a) => ({ no: porId.get(a.para), rotulo: a.rotulo }));
  const comOrigem = new Set(grafo.arestas.map((a) => a.para));
  const raizes = grafo.nos.filter((n) => !comOrigem.has(n.id));

  function Ramo({
    no,
    rotulo,
    visitados,
  }: {
    no: NoDoGrafo;
    rotulo?: string;
    visitados: Set<string>;
  }) {
    const filhos = visitados.has(no.id) ? [] : dependentesDe(no.id);
    const proximos = new Set(visitados).add(no.id);
    return (
      <li>
        <button
          type="button"
          onClick={() => aoAbrir(no)}
          className="flex min-h-11 w-full flex-col items-start rounded-controle px-2 text-left hover:bg-pedra-100"
        >
          <span className="font-semibold">{no.titulo}</span>
          <span className="font-mono text-xs text-pedra-600">
            {rotulo ? `via ${rotulo} · ` : ""}
            {no.subtitulo}
          </span>
        </button>
        {filhos.length > 0 ? (
          <ul className="ml-4 border-l-2 border-sinal-300 pl-3">
            {filhos.map((f, i) =>
              f.no ? (
                <Ramo key={`${f.no.id}-${i}`} no={f.no} rotulo={f.rotulo} visitados={proximos} />
              ) : null,
            )}
          </ul>
        ) : null}
      </li>
    );
  }

  return (
    <ul
      aria-label="Vínculos em lista"
      className="flex flex-col gap-2 rounded-cartao border border-pedra-200 bg-superficie p-3"
    >
      {(raizes.length > 0 ? raizes : grafo.nos).map((no) => (
        <Ramo key={no.id} no={no} visitados={new Set()} />
      ))}
    </ul>
  );
}
