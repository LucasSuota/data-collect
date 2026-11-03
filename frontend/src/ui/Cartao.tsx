import type { HTMLAttributes } from "react";

/** A superfície padrão: papel mais claro que o fundo, borda fina e uma sombra quase imperceptível. */
export function Cartao({ className = "", ...resto }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...resto}
      className={`rounded-cartao border border-pedra-200 bg-superficie shadow-cartao ${className}`}
    />
  );
}
