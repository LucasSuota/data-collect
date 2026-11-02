import { useId, type SelectHTMLAttributes } from "react";

interface Props extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  rotulo: string;
  /** Esconde o rótulo da vista mas o mantém para o leitor de tela (quando o contexto já o explica). */
  ocultarRotulo?: boolean;
}

/** Caixa de seleção nativa (acessível por teclado e leitor de tela), no estilo do app. */
export function Selecao({
  rotulo,
  ocultarRotulo = false,
  className = "",
  children,
  ...resto
}: Props) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className={ocultarRotulo ? "sr-only" : "text-sm font-medium text-pedra-800"}
      >
        {rotulo}
      </label>
      <select
        {...resto}
        id={id}
        className={`min-h-7 rounded-controle border border-pedra-300 bg-superficie px-2 text-[0.8125rem] text-pedra-800 transition-colors duration-(--duracao-rapida) hover:border-pedra-400 ${className}`}
      >
        {children}
      </select>
    </div>
  );
}
