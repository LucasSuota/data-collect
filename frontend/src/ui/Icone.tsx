import type { SVGProps } from "react";

/** Caminhos de um conjunto pequeno de ícones de traço (24x24), desenhados para este app. */
const CAMINHOS = {
  copiar: "M8 8h10v12H8zM6 16H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1",
  editar: "M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4",
  lixeira: "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6",
  pasta: "M3 7a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7z",
  registros: "M5 5h14M5 10h14M5 15h14M5 20h9",
  mais: "M12 5v14M5 12h14",
  seta: "M9 6l6 6-6 6",
  alca: "M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01",
  fechar: "M6 6l12 12M18 6L6 18",
  alerta: "M12 4l9 16H3L12 4zM12 10v4M12 17h.01",
  ok: "M5 12.5l4.5 4.5L19 7.5",
} as const;

export type NomeDoIcone = keyof typeof CAMINHOS;

interface Props extends Omit<SVGProps<SVGSVGElement>, "name"> {
  nome: NomeDoIcone;
  tamanho?: number;
}

/** Decorativo por padrão (`aria-hidden`): quem precisa de nome usa o texto do botão que o contém. */
export function Icone({ nome, tamanho = 16, ...resto }: Props) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...resto}
    >
      <path d={CAMINHOS[nome]} />
    </svg>
  );
}
