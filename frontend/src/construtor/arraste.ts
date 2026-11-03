import { AREA_DA_LISTA, type Arrastado, type CampoEmEdicao } from "./estado";

/**
 * Apoio ao arrastar e soltar do construtor: onde o item vai entrar e o que dizer ao leitor de
 * tela. Funções puras; a regra de aplicar o arraste continua em `aplicarArraste` (estado.ts).
 */

/** A posição (0 a n) em que um item solto sobre `alvo` entraria; `null` se não há destino. */
export function posicaoDoDestino(campos: CampoEmEdicao[], alvo: string | null): number | null {
  if (alvo === null) return null;
  if (alvo === AREA_DA_LISTA) return campos.length;
  const indice = campos.findIndex((campo) => campo.chave === alvo);
  return indice === -1 ? null : indice;
}

/** A chave do campo que existe em `depois` e não existia em `antes` (o recém-adicionado). */
export function chaveDoCampoNovo(antes: CampoEmEdicao[], depois: CampoEmEdicao[]): string | null {
  const existentes = new Set(antes.map((campo) => campo.chave));
  return depois.find((campo) => !existentes.has(campo.chave))?.chave ?? null;
}

interface EventoDeArraste {
  // O `dnd-kit` tipa `data.current` como qualquer coisa; aqui só se confia no que tem a forma certa.
  active: { id: string | number; data: { current?: unknown } };
  over?: { id: string | number } | null;
}

function arrastadoDe(evento: EventoDeArraste): Arrastado | null {
  const dados = evento.active.data.current;
  if (typeof dados !== "object" || dados === null) return null;
  const { origem } = dados as { origem?: unknown };
  if (origem === "paleta" && typeof (dados as { tipo?: unknown }).tipo === "string") {
    return dados as Arrastado;
  }
  if (origem === "campo" && typeof (dados as { chave?: unknown }).chave === "string") {
    return dados as Arrastado;
  }
  return null;
}

/** Os anúncios do arrastar e soltar para leitor de tela, em português. */
export function anunciosDoConstrutor(contexto: {
  campos: () => CampoEmEdicao[];
  rotuloDoTipo: (tipo: string) => string;
}) {
  const nomeDoCampo = (chave: string) =>
    contexto.campos().find((campo) => campo.chave === chave)?.rotulo || "(sem rótulo)";
  const alvoDe = (evento: EventoDeArraste) => (evento.over ? String(evento.over.id) : null);

  return {
    onDragStart(evento: EventoDeArraste) {
      const arrastado = arrastadoDe(evento);
      if (!arrastado) return undefined;
      return arrastado.origem === "paleta"
        ? `Você pegou o tipo ${contexto.rotuloDoTipo(arrastado.tipo)}. Solte na lista para adicionar um campo.`
        : `Você pegou o campo ${nomeDoCampo(arrastado.chave)}.`;
    },
    onDragOver(evento: EventoDeArraste) {
      if (!arrastadoDe(evento)) return undefined;
      const campos = contexto.campos();
      const alvo = alvoDe(evento);
      if (alvo === AREA_DA_LISTA) return "No fim da lista.";
      const posicao = posicaoDoDestino(campos, alvo);
      if (alvo === null || posicao === null) return "Fora da lista.";
      return `Sobre o campo ${nomeDoCampo(alvo)}, posição ${posicao + 1} de ${campos.length}.`;
    },
    onDragEnd(evento: EventoDeArraste) {
      const arrastado = arrastadoDe(evento);
      if (!arrastado) return undefined;
      const campos = contexto.campos();
      const posicao = posicaoDoDestino(campos, alvoDe(evento));
      if (posicao === null) return "Solto fora da lista. Nada mudou.";
      if (arrastado.origem === "paleta") {
        return `Campo ${contexto.rotuloDoTipo(arrastado.tipo)} adicionado na posição ${posicao + 1}.`;
      }
      // Na área da lista o campo vai para o fim: a posição final é a do último, já sem ele.
      const final = alvoDe(evento) === AREA_DA_LISTA ? campos.length : posicao + 1;
      return `O campo ${nomeDoCampo(arrastado.chave)} foi movido para a posição ${final}.`;
    },
    onDragCancel(evento: EventoDeArraste) {
      return arrastadoDe(evento) ? "Movimento cancelado." : undefined;
    },
  };
}

export const INSTRUCOES_DO_CONSTRUTOR =
  "Para arrastar, pressione espaço ou Enter, use as setas para escolher a posição e pressione " +
  "espaço ou Enter de novo para soltar. Esc cancela. Também há os botões de mover para cima e para baixo.";
