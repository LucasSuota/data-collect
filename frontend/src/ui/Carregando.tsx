import { useEffect, useState, type ReactNode } from "react";

interface Props {
  /** O que o leitor de tela anuncia ("Carregando formulários"). */
  rotulo: string;
  /** Espera antes de mostrar o esqueleto: resposta rápida não deve piscar. */
  atrasoMs?: number;
  children: ReactNode;
}

/** Envolve um esqueleto com o aviso de "ocupado" e o atraso antes de aparecer. */
export function Carregando({ rotulo, atrasoMs = 150, children }: Props) {
  const [visivel, setVisivel] = useState(atrasoMs === 0);

  useEffect(() => {
    if (atrasoMs === 0) return;
    const temporizador = setTimeout(() => setVisivel(true), atrasoMs);
    return () => clearTimeout(temporizador);
  }, [atrasoMs]);

  if (!visivel) return null;
  return (
    <div role="status" aria-label={rotulo} aria-busy="true">
      {children}
    </div>
  );
}
