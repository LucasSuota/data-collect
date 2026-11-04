/** Uma citação do assistente: o rótulo e para onde ela leva (registro, formulário ou guia). */
export interface Citacao {
  rotulo: string;
  href: string | null;
}

export function lerCitacoes(brutas: Record<string, unknown>[]): Citacao[] {
  return brutas.map((c) => {
    const rotulo = typeof c["rotulo"] === "string" ? c["rotulo"] : "Fonte";
    switch (c["tipo"]) {
      case "registro":
        return {
          rotulo,
          href: typeof c["registro_id"] === "number" ? `#/registros/${c["registro_id"]}` : null,
        };
      case "formulario":
        return {
          rotulo,
          href:
            typeof c["formulario_id"] === "number"
              ? `#/formularios/${c["formulario_id"]}/registros`
              : null,
        };
      case "ajuda":
        return {
          rotulo,
          href:
            typeof c["arquivo"] === "string"
              ? `#/ajuda/${encodeURIComponent(c["arquivo"].replace(/\.md$/, ""))}`
              : null,
        };
      default:
        return { rotulo, href: null }; // tipo desconhecido: mostra a fonte sem link, nunca inventa um
    }
  });
}
