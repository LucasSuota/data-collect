import type { NomeDoIcone } from "../ui";
import type { Rota } from "../rotas";

export interface ItemDeNavegacao {
  id: string;
  rotulo: string;
  icone: NomeDoIcone;
  destino: Rota;
  /** Nomes de rota em que o item aparece como o atual. */
  ativoEm: Rota["nome"][];
  grupo: "trabalho" | "administracao";
  /** Sem a permissão, o item some: a pessoa não esperaria encontrá-lo (AGENTS.md §2.11). */
  permissao?: string;
}

export const ITENS: ItemDeNavegacao[] = [
  {
    id: "inicio",
    rotulo: "Início",
    icone: "casa",
    destino: { nome: "inicio" },
    ativoEm: ["inicio", "busca"],
    grupo: "trabalho",
  },
  {
    id: "formularios",
    rotulo: "Formulários",
    icone: "documento",
    destino: { nome: "formularios" },
    ativoEm: [
      "formularios",
      "pasta",
      "novoFormulario",
      "editarFormulario",
      "criarComIa",
      "exemplos",
    ],
    grupo: "trabalho",
    permissao: "formularios:ver",
  },
  {
    id: "mapa",
    rotulo: "Mapa de vínculos",
    icone: "mapa",
    destino: { nome: "mapa" },
    ativoEm: ["mapa"],
    grupo: "trabalho",
    permissao: "formularios:ver",
  },
  {
    id: "registros",
    rotulo: "Registros",
    icone: "registros",
    destino: { nome: "registrosRecentes" },
    ativoEm: ["registrosRecentes", "registros", "registro", "novoRegistro"],
    grupo: "trabalho",
    permissao: "registros:ver",
  },
  {
    id: "assistente",
    rotulo: "Assistente",
    icone: "conversa",
    destino: { nome: "chat" },
    ativoEm: ["chat"],
    grupo: "trabalho",
    permissao: "ia:assistente",
  },
  {
    id: "equipe",
    rotulo: "Equipe",
    icone: "usuarios",
    destino: { nome: "equipe" },
    ativoEm: ["equipe"],
    grupo: "administracao",
    permissao: "equipe:ver",
  },
  {
    id: "cargos",
    rotulo: "Cargos e permissões",
    icone: "escudo",
    destino: { nome: "cargos" },
    ativoEm: ["cargos"],
    grupo: "administracao",
    permissao: "cargos:editar",
  },
  {
    id: "ia",
    rotulo: "Inteligência artificial",
    icone: "brilho",
    destino: { nome: "ia" },
    ativoEm: ["ia"],
    grupo: "administracao",
    permissao: "cargos:editar",
  },
];

/** Os itens que a pessoa pode ver: a navegação deriva das permissões, nunca do nome do cargo. */
export function itensVisiveis(pode: (permissao: string) => boolean): ItemDeNavegacao[] {
  return ITENS.filter((item) => item.permissao === undefined || pode(item.permissao));
}

export interface ItemDaBarraInferior {
  tipo: "item" | "novo";
  item?: ItemDeNavegacao;
}

/**
 * A barra de baixo (celular): até quatro destinos e, no meio, o botão de novo registro para quem
 * pode criar. O resto fica na tela "Perfil", que a barra de cima alcança.
 */
export function barraInferior(pode: (permissao: string) => boolean): ItemDaBarraInferior[] {
  const principais = itensVisiveis(pode)
    .filter((i) => ["inicio", "formularios", "registros", "mapa", "equipe"].includes(i.id))
    .slice(0, 4)
    .map((item): ItemDaBarraInferior => ({ tipo: "item", item }));
  if (!pode("registros:criar")) return principais;
  const meio = Math.ceil(principais.length / 2);
  return [...principais.slice(0, meio), { tipo: "novo" }, ...principais.slice(meio)];
}

export function itemAtual(itens: ItemDeNavegacao[], rota: Rota): ItemDeNavegacao | undefined {
  return itens.find((i) => i.ativoEm.includes(rota.nome));
}
