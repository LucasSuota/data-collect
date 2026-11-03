import type { Aresta } from "./grafo";
import { LARGURA_DO_NO } from "./medidas";
import type { Posicao } from "./layout";

interface Props {
  arestas: Aresta[];
  posicoes: Map<string, Posicao>;
  alturas: Map<string, number>;
  largura: number;
  altura: number;
  /** Ids das arestas da cadeia selecionada; `null` quando nada está selecionado. */
  realce: ReadonlySet<string> | null;
}

const LIMITE_DO_ROTULO = 28;
const cortar = (texto: string) =>
  texto.length > LIMITE_DO_ROTULO ? `${texto.slice(0, LIMITE_DO_ROTULO - 1)}…` : texto;

/** As ligações entre os cartões: curvas da porta da direita da origem à da esquerda do dependente. */
export function Arestas({ arestas, posicoes, alturas, largura, altura, realce }: Props) {
  return (
    <svg
      width={largura}
      height={altura}
      className="pointer-events-none absolute top-0 left-0 overflow-visible"
      aria-hidden="true"
    >
      <defs>
        {(["neutra", "realce"] as const).map((tipo) => (
          <marker
            key={tipo}
            id={`ponta-${tipo}`}
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="9"
            markerHeight="9"
            markerUnits="userSpaceOnUse"
            orient="auto"
          >
            <path
              d="M1 1l8 4-8 4z"
              fill={tipo === "realce" ? "var(--color-sinal-500)" : "var(--color-pedra-500)"}
            />
          </marker>
        ))}
      </defs>
      {arestas.map((aresta) => {
        const de = posicoes.get(aresta.de);
        const para = posicoes.get(aresta.para);
        if (!de || !para) return null;
        const x1 = de.x + LARGURA_DO_NO;
        const y1 = de.y + (alturas.get(aresta.de) ?? 0) / 2;
        const x2 = para.x;
        const y2 = para.y + (alturas.get(aresta.para) ?? 0) / 2;
        const curva = Math.max(48, (x2 - x1) / 2);
        const destacada = realce?.has(aresta.id) ?? false;
        const apagada = realce !== null && !destacada;
        return (
          <g
            key={aresta.id}
            className={`transition-opacity duration-(--duracao-normal) ${apagada ? "opacity-25" : ""}`}
          >
            <path
              d={`M${x1},${y1} C${x1 + curva},${y1} ${x2 - curva},${y2} ${x2},${y2}`}
              fill="none"
              stroke={destacada ? "var(--color-sinal-500)" : "var(--color-pedra-400)"}
              strokeWidth={destacada ? 2.5 : 1.75}
              markerEnd={`url(#ponta-${destacada ? "realce" : "neutra"})`}
            />
            {aresta.rotulo ? (
              <text
                x={(x1 + x2) / 2}
                y={(y1 + y2) / 2 - 8}
                textAnchor="middle"
                className="fill-pedra-600 text-[11px]"
                style={{ paintOrder: "stroke", stroke: "var(--color-superficie)", strokeWidth: 4 }}
              >
                {cortar(aresta.rotulo)}
              </text>
            ) : null}
          </g>
        );
      })}
    </svg>
  );
}
