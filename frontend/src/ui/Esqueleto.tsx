import type { HTMLAttributes } from "react";

/**
 * Um bloco de esqueleto: cinza, com um pulso suave (o `prefers-reduced-motion` o deixa parado).
 * É decorativo: escondido do leitor de tela, que ouve o rótulo do `Carregando` que o envolve.
 */
export function Esqueleto({ className = "", ...resto }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...resto}
      aria-hidden="true"
      className={`animate-brilho rounded-controle bg-pedra-200 ${className}`}
    />
  );
}
