import type { Pasta } from "../api/cliente";

/**
 * Lógica pura da árvore de pastas. A API devolve uma lista plana (`pasta_pai_id`); o front só a
 * organiza para mostrar. Ciclo e nome repetido são regras do servidor: aqui, no máximo, se esconde
 * o que o servidor recusaria (por exemplo, mover uma pasta para dentro dela mesma).
 */
export type { Pasta };

export interface NoDaArvore {
  pasta: Pasta;
  filhos: NoDaArvore[];
}

const comparar = (a: Pasta, b: Pasta) =>
  a.nome.localeCompare(b.nome, "pt-BR", { sensitivity: "base" }) || a.id - b.id;

/** Monta a árvore; irmãos por nome. Pasta com pai ausente da lista vai para a raiz, e não some. */
export function montarArvore(pastas: Pasta[]): NoDaArvore[] {
  const nos = new Map<number, NoDaArvore>(pastas.map((p) => [p.id, { pasta: p, filhos: [] }]));
  const raizes: NoDaArvore[] = [];
  for (const no of nos.values()) {
    const pai = no.pasta.pasta_pai_id === null ? undefined : nos.get(no.pasta.pasta_pai_id);
    (pai ? pai.filhos : raizes).push(no);
  }
  const ordenar = (lista: NoDaArvore[]) => {
    lista.sort((a, b) => comparar(a.pasta, b.pasta));
    lista.forEach((no) => ordenar(no.filhos));
  };
  ordenar(raizes);
  return raizes;
}

/** As pastas da raiz até `pastaId` (vazio para a raiz ou para uma pasta que não existe). */
export function caminhoAte(pastas: Pasta[], pastaId: number | null): Pasta[] {
  const porId = new Map(pastas.map((p) => [p.id, p]));
  const caminho: Pasta[] = [];
  const vistas = new Set<number>();
  let atual = pastaId === null ? undefined : porId.get(pastaId);
  while (atual && !vistas.has(atual.id)) {
    vistas.add(atual.id);
    caminho.unshift(atual);
    atual = atual.pasta_pai_id === null ? undefined : porId.get(atual.pasta_pai_id);
  }
  return caminho;
}

/** A pasta e todas as suas descendentes. */
export function idsDaSubarvore(pastas: Pasta[], pastaId: number): Set<number> {
  const ids = new Set<number>([pastaId]);
  let cresceu = true;
  while (cresceu) {
    cresceu = false;
    for (const p of pastas) {
      if (p.pasta_pai_id !== null && ids.has(p.pasta_pai_id) && !ids.has(p.id)) {
        ids.add(p.id);
        cresceu = true;
      }
    }
  }
  return ids;
}

export interface Destino {
  id: number;
  /** O caminho completo ("Obras / Fundação"), para distinguir pastas de mesmo nome. */
  rotulo: string;
}

/** Pastas para onde algo pode ser movido, em ordem de árvore; `mover` esconde essa subárvore. */
export function destinosDeMovimento(pastas: Pasta[], mover?: number): Destino[] {
  const escondidas = mover === undefined ? new Set<number>() : idsDaSubarvore(pastas, mover);
  const destinos: Destino[] = [];
  const percorrer = (nos: NoDaArvore[], prefixo: string) => {
    for (const no of nos) {
      const rotulo = prefixo ? `${prefixo} / ${no.pasta.nome}` : no.pasta.nome;
      if (!escondidas.has(no.pasta.id)) destinos.push({ id: no.pasta.id, rotulo });
      percorrer(no.filhos, rotulo);
    }
  };
  percorrer(montarArvore(pastas), "");
  return destinos;
}

export const ID_DA_RAIZ = "pasta-raiz";
export const idDeArraste = (formularioId: number) => `formulario-${formularioId}`;
export const idDeDestino = (pastaId: number) => `pasta-${pastaId}`;

const INTEIRO = /^[1-9]\d*$/;

function numeroDepois(prefixo: string, id: string): number | null {
  if (!id.startsWith(prefixo)) return null;
  const resto = id.slice(prefixo.length);
  return INTEIRO.test(resto) ? Number(resto) : null;
}

/** Traduz "formulário X solto sobre Y" no movimento a pedir ao servidor; `null` = nada a fazer. */
export function resolverMovimento(
  arrastado: string,
  destino: string | null,
): { formularioId: number; pastaId: number | null } | null {
  const formularioId = numeroDepois("formulario-", arrastado);
  if (formularioId === null || destino === null) return null;
  if (destino === ID_DA_RAIZ) return { formularioId, pastaId: null };
  const pastaId = numeroDepois("pasta-", destino);
  return pastaId === null ? null : { formularioId, pastaId };
}

interface EventoDeArraste {
  active: { id: string | number };
  over?: { id: string | number } | null;
}

/**
 * Os anúncios do arrastar e soltar para leitor de tela, em português (o padrão do `dnd-kit` é em
 * inglês). `nomes` resolve o id de arraste/destino no nome que a pessoa vê.
 */
export function anunciosDeArraste(nomes: {
  formulario: (id: string) => string | null;
  destino: (id: string) => string | null;
}) {
  const doFormulario = (evento: EventoDeArraste) => nomes.formulario(String(evento.active.id));
  const doDestino = (evento: EventoDeArraste) =>
    evento.over ? nomes.destino(String(evento.over.id)) : null;

  return {
    onDragStart(evento: EventoDeArraste) {
      const formulario = doFormulario(evento);
      return formulario === null ? undefined : `Você pegou o formulário ${formulario}.`;
    },
    onDragOver(evento: EventoDeArraste) {
      const formulario = doFormulario(evento);
      if (formulario === null) return undefined;
      const destino = doDestino(evento);
      return destino === null
        ? `O formulário ${formulario} não está sobre nenhuma pasta.`
        : `O formulário ${formulario} está sobre a pasta ${destino}.`;
    },
    onDragEnd(evento: EventoDeArraste) {
      const formulario = doFormulario(evento);
      if (formulario === null) return undefined;
      const destino = doDestino(evento);
      return destino === null
        ? `O formulário ${formulario} foi solto fora de uma pasta. Nada mudou.`
        : `O formulário ${formulario} foi solto na pasta ${destino}.`;
    },
    onDragCancel(evento: EventoDeArraste) {
      const formulario = doFormulario(evento);
      return formulario === null
        ? undefined
        : `Movimento cancelado. O formulário ${formulario} ficou onde estava.`;
    },
  };
}

export const INSTRUCOES_DE_ARRASTE =
  "Para mover o formulário, pressione espaço ou Enter, use as setas para escolher a pasta e " +
  "pressione espaço ou Enter de novo para soltar. Esc cancela.";
