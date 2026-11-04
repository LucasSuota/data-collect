/**
 * Criar um vínculo pelo mapa é adicionar um campo `referencia` ao **rascunho da próxima versão**
 * do dependente (AGENTS.md §2.7): versões publicadas nunca mudam, e o servidor continua
 * rejeitando ciclos ao publicar. Aqui só se monta o campo; quem valida é o servidor.
 */

const RESERVADOS = new Set(["pi", "se", "min", "max", "media", "soma", "dias"]);

type CampoBruto = Record<string, unknown>;

/** Um `id` de campo válido a partir do nome do formulário de origem (sem acento, sem `__`). */
export function idDaReferencia(nomeDaOrigem: string, idsExistentes: ReadonlySet<string>): string {
  const base =
    nomeDaOrigem
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .replace(/^(\d)/, "ref_$1") || "origem";
  const inicial = RESERVADOS.has(base) ? `${base}_ref` : base;
  let candidato = inicial;
  for (let n = 2; idsExistentes.has(candidato); n++) candidato = `${inicial}_${n}`;
  return candidato;
}

export interface ResultadoDoVinculo {
  definicao: { campos: CampoBruto[]; [chave: string]: unknown };
  campoId: string;
  /** Já havia uma referência àquela origem: nada foi adicionado. */
  jaExistia: boolean;
}

export function adicionarReferencia(definicao: unknown, nomeDaOrigem: string): ResultadoDoVinculo {
  const base =
    typeof definicao === "object" && definicao !== null
      ? (definicao as Record<string, unknown>)
      : {};
  const campos = Array.isArray(base["campos"]) ? (base["campos"] as CampoBruto[]) : [];
  const existente = campos.find(
    (c) =>
      c["tipo"] === "referencia" &&
      typeof c["formulario"] === "string" &&
      c["formulario"].trim().toLowerCase() === nomeDaOrigem.trim().toLowerCase(),
  );
  if (existente) {
    return {
      definicao: { ...base, campos },
      campoId: String(existente["id"]),
      jaExistia: true,
    };
  }
  const ids = new Set(campos.map((c) => String(c["id"])));
  const campoId = idDaReferencia(nomeDaOrigem, ids);
  const novo: CampoBruto = {
    id: campoId,
    tipo: "referencia",
    rotulo: nomeDaOrigem,
    formulario: nomeDaOrigem,
    obrigatorio: false,
  };
  return { definicao: { ...base, campos: [...campos, novo] }, campoId, jaExistia: false };
}
