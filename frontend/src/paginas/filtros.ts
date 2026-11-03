import type { ResumoDeFormulario } from "../api/cliente";
import { caminhoAte, idsDaSubarvore, type NoDaArvore, type Pasta } from "./pastas";

/**
 * Busca e ordenação da tela de formulários. Só organiza o que a API já devolveu: a lista é pequena
 * e local, então filtrar no cliente evita uma ida ao servidor a cada tecla.
 */
export type OrdemDaLista = "nome-asc" | "nome-desc" | "recentes" | "antigos";

/** `tudo` procura em todas as pastas; `pasta` só na aberta e nas descendentes. */
export type EscopoDaBusca = "tudo" | "pasta";

export const ORDENS: { valor: OrdemDaLista; rotulo: string }[] = [
  { valor: "nome-asc", rotulo: "Nome (A–Z)" },
  { valor: "nome-desc", rotulo: "Nome (Z–A)" },
  { valor: "recentes", rotulo: "Mais recentes" },
  { valor: "antigos", rotulo: "Mais antigos" },
];

/** Minúsculas e sem acento, para "fundacao" achar "Fundação". */
export function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("pt-BR")
    .trim();
}

/** Todas as palavras da busca precisam aparecer no texto, em qualquer ordem. */
export function combinaComBusca(texto: string, termo: string): boolean {
  const palavras = normalizar(termo).split(/\s+/).filter(Boolean);
  const alvo = normalizar(texto);
  return palavras.every((palavra) => alvo.includes(palavra));
}

const porNome = (a: { nome: string }, b: { nome: string }) =>
  a.nome.localeCompare(b.nome, "pt-BR", { sensitivity: "base" });

function ordenarFormularios(
  formularios: ResumoDeFormulario[],
  ordem: OrdemDaLista,
): ResumoDeFormulario[] {
  const criacao = (f: ResumoDeFormulario) => Date.parse(f.criado_em);
  const comparar: Record<OrdemDaLista, (a: ResumoDeFormulario, b: ResumoDeFormulario) => number> = {
    "nome-asc": porNome,
    "nome-desc": (a, b) => porNome(b, a),
    recentes: (a, b) => criacao(b) - criacao(a) || porNome(a, b),
    antigos: (a, b) => criacao(a) - criacao(b) || porNome(a, b),
  };
  return [...formularios].sort(comparar[ordem]);
}

/** Pastas não têm data na lista: seguem o nome, e só "Z–A" inverte. */
function ordenarPastas(pastas: Pasta[], ordem: OrdemDaLista): Pasta[] {
  const ordenadas = [...pastas].sort((a, b) => porNome(a, b) || a.id - b.id);
  return ordem === "nome-desc" ? ordenadas.reverse() : ordenadas;
}

interface Entrada {
  formularios: ResumoDeFormulario[];
  pastas: Pasta[];
  /** A pasta aberta; `null` é a raiz. */
  atualId: number | null;
  termo: string;
  escopo: EscopoDaBusca;
  ordem: OrdemDaLista;
}

/**
 * O que a tela mostra. Sem busca: o conteúdo direto da pasta aberta. Com busca: pastas e
 * formulários de qualquer nível cujo nome combine, limitados à pasta aberta se o escopo pedir.
 */
export function listarDaTela({ formularios, pastas, atualId, termo, escopo, ordem }: Entrada): {
  pastas: Pasta[];
  formularios: ResumoDeFormulario[];
} {
  if (termo.trim() === "") {
    return {
      pastas: ordenarPastas(
        pastas.filter((p) => p.pasta_pai_id === atualId),
        ordem,
      ),
      formularios: ordenarFormularios(
        formularios.filter((f) => (f.pasta_id ?? null) === atualId),
        ordem,
      ),
    };
  }

  const limite = escopo === "pasta" && atualId !== null ? idsDaSubarvore(pastas, atualId) : null;
  return {
    pastas: ordenarPastas(
      pastas.filter(
        (p) =>
          (limite === null || (limite.has(p.id) && p.id !== atualId)) &&
          combinaComBusca(p.nome, termo),
      ),
      ordem,
    ),
    formularios: ordenarFormularios(
      formularios.filter(
        (f) =>
          (limite === null || (f.pasta_id != null && limite.has(f.pasta_id))) &&
          combinaComBusca(f.nome, termo),
      ),
      ordem,
    ),
  };
}

/** "Obras / Fundação" para dizer onde um resultado está; sem pasta, "Sem pasta". */
export function rotuloDoCaminho(pastas: Pasta[], pastaId: number | null): string {
  const caminho = caminhoAte(pastas, pastaId);
  return caminho.length === 0 ? "Sem pasta" : caminho.map((p) => p.nome).join(" / ");
}

/**
 * A árvore só com o que combina: a pasta que combina (com tudo o que há dentro dela) e o caminho
 * até as descendentes que combinam. Sem busca, devolve a mesma árvore.
 */
export function filtrarArvore(nos: NoDaArvore[], termo: string): NoDaArvore[] {
  if (termo.trim() === "") return nos;
  const resultado: NoDaArvore[] = [];
  for (const no of nos) {
    if (combinaComBusca(no.pasta.nome, termo)) {
      resultado.push(no);
      continue;
    }
    const filhos = filtrarArvore(no.filhos, termo);
    if (filhos.length > 0) resultado.push({ pasta: no.pasta, filhos });
  }
  return resultado;
}
