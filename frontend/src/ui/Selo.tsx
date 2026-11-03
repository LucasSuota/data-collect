import type { ReactNode } from "react";

/** Etiqueta curta de metadado (por exemplo, "v3"): fonte mono, sem competir com o título. */
export function Selo({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-controle bg-pedra-100 px-1.5 py-0.5 font-mono text-xs text-pedra-600">
      {children}
    </span>
  );
}
