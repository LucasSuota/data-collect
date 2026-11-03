import type { ButtonHTMLAttributes } from "react";

type Variante = "primario" | "secundario" | "fantasma" | "perigo" | "perigoSolido";
type Tamanho = "normal" | "pequeno";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante;
  tamanho?: Tamanho;
  /** Mostra que a ação está em andamento e bloqueia novos cliques. */
  carregando?: boolean;
}

const VARIANTES: Record<Variante, string> = {
  primario: "bg-pedra-900 text-superficie hover:bg-pedra-700 border border-pedra-900",
  secundario: "bg-superficie text-pedra-800 border border-pedra-300 hover:bg-pedra-100",
  fantasma: "bg-transparent text-pedra-700 border border-transparent hover:bg-pedra-200/60",
  perigo: "bg-superficie text-erro-700 border border-erro-300 hover:bg-erro-50",
  perigoSolido: "bg-erro-700 text-superficie border border-erro-700 hover:bg-erro-700/90",
};

const TAMANHOS: Record<Tamanho, string> = {
  normal: "min-h-9 px-3.5 text-sm",
  pequeno: "min-h-7 px-2.5 text-[0.8125rem]",
};

/** O botão do app. `type="button"` por padrão: botão dentro de formulário não envia sem querer. */
export function Botao({
  variante = "secundario",
  tamanho = "normal",
  carregando = false,
  type = "button",
  disabled,
  className = "",
  children,
  ...resto
}: Props) {
  return (
    <button
      {...resto}
      type={type}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      className={[
        "inline-flex items-center justify-center gap-1.5 rounded-controle font-medium",
        "transition-colors duration-(--duracao-rapida) disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTES[variante],
        TAMANHOS[tamanho],
        className,
      ].join(" ")}
    >
      {children}
    </button>
  );
}
