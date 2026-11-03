import type { ReactNode } from "react";
import { Icone, type NomeDoIcone } from "./Icone";

type Tom = "erro" | "sucesso" | "info";

const TONS: Record<Tom, { caixa: string; icone: NomeDoIcone }> = {
  erro: { caixa: "border-erro-300 bg-erro-50 text-erro-700", icone: "alerta" },
  sucesso: { caixa: "border-sucesso-300 bg-sucesso-50 text-sucesso-700", icone: "ok" },
  info: { caixa: "border-pedra-300 bg-pedra-100 text-pedra-700", icone: "alerta" },
};

interface Props {
  tom: Tom;
  children: ReactNode;
  /** Ações ao lado do texto (por exemplo, "Editar a cópia"). */
  acoes?: ReactNode;
}

/** Erro é `role="alert"` (interrompe o leitor de tela); sucesso e informação são `role="status"`. */
export function Aviso({ tom, children, acoes }: Props) {
  const { caixa, icone } = TONS[tom];
  return (
    <div
      role={tom === "erro" ? "alert" : "status"}
      className={`flex flex-wrap items-center gap-x-3 gap-y-2 rounded-controle border px-3.5 py-2.5 text-sm ${caixa}`}
    >
      <Icone nome={icone} className="shrink-0" />
      <p className="min-w-0 flex-1">{children}</p>
      {acoes}
    </div>
  );
}
