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
  busca: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  mapa: "M4 5h6v5H4zM14 14h6v5h-6zM10 7.5h2.5a2 2 0 0 1 2 2V14M4 16h6v3H4z",
  elo: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  menos: "M5 12h14",
  ajustar: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  entrada: "M4 12h13M12 6l6 6-6 6",
  abrir: "M14 5h5v5M19 5l-8 8M10 6H6a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-4",
  cadeado: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  casa: "M4 11l8-7 8 7M6 10v10h12V10",
  documento: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5",
  usuarios:
    "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM3 20a6 6 0 0 1 12 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14a6 6 0 0 1 3 6",
  usuario: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  escudo: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
  sino: "M6 17v-6a6 6 0 0 1 12 0v6l1.5 2h-15zM10 21h4",
  brilho: "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2zM19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z",
  ajuda:
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01",
  conversa: "M4 5h16v11H9l-5 4z",
  pino: "M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  voltar: "M15 6l-6 6 6 6",
  pontos: "M12 6h.01M12 12h.01M12 18h.01",
  olho: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  baixar: "M12 4v12M7 11l5 5 5-5M5 20h14",
  funil: "M4 5h16l-6 8v6l-4-2v-4z",
  sair: "M10 5H5v14h5M15 8l4 4-4 4M19 12H9",
  historico: "M12 7v5l3 2M3 12a9 9 0 1 0 3-6.7M3 4v4h4",
  confirmado: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 12.5l3 3 5-6",
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
