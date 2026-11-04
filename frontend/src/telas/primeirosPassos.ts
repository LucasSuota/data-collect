export interface PassoDoChecklist {
  id: string;
  rotulo: string;
  feito: boolean;
  /** Onde a pessoa faz o passo; ausente quando ela não tem a permissão para isso. */
  href?: string;
}

export interface EstadoDaEquipe {
  formularios: number;
  registros: number;
  pessoas: number;
}

/**
 * O checklist "Primeiros passos" é marcado pelo **estado real** da equipe (AGENTS.md §2.16): ter
 * formulário, ter registro e ter mais alguém além de você. Passo sem permissão não aparece.
 */
export function passosDoChecklist(
  estado: EstadoDaEquipe,
  pode: (permissao: string) => boolean,
): PassoDoChecklist[] {
  const passos: PassoDoChecklist[] = [];
  if (pode("formularios:publicar")) {
    passos.push({
      id: "formulario",
      rotulo: "Criar o primeiro formulário (ou importar um exemplo)",
      feito: estado.formularios > 0,
      href: estado.formularios > 0 ? "#/formularios" : "#/exemplos",
    });
  }
  if (pode("registros:criar")) {
    passos.push({
      id: "registro",
      rotulo: "Preencher o primeiro registro",
      feito: estado.registros > 0,
      href: "#/formularios",
    });
  }
  if (pode("equipe:convidar")) {
    passos.push({
      id: "convite",
      rotulo: "Convidar alguém da sua equipe",
      feito: estado.pessoas > 1,
      href: "#/equipe",
    });
  }
  return passos;
}
