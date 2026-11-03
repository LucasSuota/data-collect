import { useDroppable } from "@dnd-kit/core";
import { useState } from "react";
import { Icone } from "../ui";
import { ID_DA_RAIZ, idDeDestino, montarArvore, type NoDaArvore, type Pasta } from "./pastas";

interface Props {
  pastas: Pasta[];
  /** A pasta aberta agora; `null` é a raiz. */
  atual: number | null;
  /** Formulários diretos de cada pasta (`null` = sem pasta), para o contador. */
  contagem: Map<number | null, number>;
  abrir: (pastaId: number | null) => void;
}

/** A árvore lateral: a raiz e todas as pastas, cada uma também um destino de arraste. */
export function ArvoreDePastas({ pastas, atual, contagem, abrir }: Props) {
  const [recolhidas, setRecolhidas] = useState<Set<number>>(new Set());

  function alternar(pastaId: number) {
    setRecolhidas((anteriores) => {
      const novas = new Set(anteriores);
      if (!novas.delete(pastaId)) novas.add(pastaId);
      return novas;
    });
  }

  return (
    <nav aria-label="Navegação por pastas">
      <ul role="tree" aria-label="Pastas" className="flex flex-col gap-0.5">
        <Raiz
          selecionada={atual === null}
          total={contagem.get(null) ?? 0}
          abrir={() => abrir(null)}
        />
        {montarArvore(pastas).map((no) => (
          <No
            key={no.pasta.id}
            no={no}
            nivel={0}
            atual={atual}
            contagem={contagem}
            recolhidas={recolhidas}
            alternar={alternar}
            abrir={abrir}
          />
        ))}
      </ul>
    </nav>
  );
}

const LINHA =
  "group flex min-h-8 items-center gap-1.5 rounded-controle pr-2 text-sm transition-colors duration-(--duracao-rapida)";

function estiloDaLinha(selecionada: boolean, sobre: boolean) {
  if (sobre) return "bg-sinal-100 outline outline-2 -outline-offset-2 outline-sinal-500";
  return selecionada
    ? "bg-pedra-200/70 font-medium text-pedra-900"
    : "text-pedra-700 hover:bg-pedra-200/50";
}

function Raiz({
  selecionada,
  total,
  abrir,
}: {
  selecionada: boolean;
  total: number;
  abrir: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: ID_DA_RAIZ });
  return (
    <li role="treeitem" aria-selected={selecionada} aria-label="Todos os formulários">
      <div ref={setNodeRef} className={`${LINHA} ${estiloDaLinha(selecionada, isOver)}`}>
        <button
          type="button"
          aria-label="Abrir Todos os formulários"
          className="flex min-h-8 flex-1 items-center gap-2 rounded-controle pl-2 text-left"
          onClick={abrir}
        >
          <Icone nome="registros" className="shrink-0 text-pedra-500" />
          <span className="flex-1 truncate">Todos os formulários</span>
          <Contador valor={total} />
        </button>
      </div>
    </li>
  );
}

function No({
  no,
  nivel,
  atual,
  contagem,
  recolhidas,
  alternar,
  abrir,
}: {
  no: NoDaArvore;
  nivel: number;
  atual: number | null;
  contagem: Map<number | null, number>;
  recolhidas: Set<number>;
  alternar: (pastaId: number) => void;
  abrir: (pastaId: number | null) => void;
}) {
  const { pasta, filhos } = no;
  const { setNodeRef, isOver } = useDroppable({ id: idDeDestino(pasta.id) });
  const aberta = !recolhidas.has(pasta.id);
  const selecionada = atual === pasta.id;

  return (
    <li
      role="treeitem"
      aria-label={pasta.nome}
      aria-selected={selecionada}
      aria-expanded={filhos.length > 0 ? aberta : undefined}
    >
      <div
        ref={setNodeRef}
        className={`${LINHA} ${estiloDaLinha(selecionada, isOver)}`}
        style={{ paddingLeft: `${nivel * 14}px` }}
      >
        {filhos.length > 0 ? (
          <button
            type="button"
            aria-label={`${aberta ? "Recolher" : "Expandir"} ${pasta.nome}`}
            className="grid size-6 shrink-0 place-items-center rounded-controle text-pedra-500 hover:bg-pedra-200"
            onClick={() => alternar(pasta.id)}
          >
            <Icone
              nome="seta"
              tamanho={14}
              className={`transition-transform duration-(--duracao-rapida) ${aberta ? "rotate-90" : ""}`}
            />
          </button>
        ) : (
          <span className="size-6 shrink-0" aria-hidden="true" />
        )}
        <button
          type="button"
          aria-label={`Abrir a pasta ${pasta.nome}`}
          className="flex min-h-8 flex-1 items-center gap-2 rounded-controle text-left"
          onClick={() => abrir(pasta.id)}
        >
          <Icone nome="pasta" className="shrink-0 text-pedra-500" />
          <span className="flex-1 truncate">{pasta.nome}</span>
          <Contador valor={contagem.get(pasta.id) ?? 0} />
        </button>
      </div>
      {filhos.length > 0 && aberta ? (
        <ul role="group" className="flex flex-col gap-0.5">
          {filhos.map((filho) => (
            <No
              key={filho.pasta.id}
              no={filho}
              nivel={nivel + 1}
              atual={atual}
              contagem={contagem}
              recolhidas={recolhidas}
              alternar={alternar}
              abrir={abrir}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Contador({ valor }: { valor: number }) {
  if (valor === 0) return null;
  return <span className="font-mono text-xs text-pedra-500">{valor}</span>;
}
