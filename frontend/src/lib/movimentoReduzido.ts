import { useEffect, useState } from "react";

const CONSULTA = "(prefers-reduced-motion: reduce)";

function pedeMenosMovimento(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia(CONSULTA).matches;
}

/**
 * Se a pessoa pediu menos movimento ao sistema. O CSS já desliga transições e animações; isto serve
 * ao que o CSS não alcança, como a animação de soltar do `dnd-kit` (feita em JavaScript).
 */
export function useMovimentoReduzido(): boolean {
  const [reduzido, setReduzido] = useState(pedeMenosMovimento);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const consulta = window.matchMedia(CONSULTA);
    const aoMudar = () => setReduzido(consulta.matches);
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, []);

  return reduzido;
}
