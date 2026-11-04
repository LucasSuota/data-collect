import type { EstadoDoRegistro } from "../api/cliente";
import { Icone, type NomeDoIcone } from "./Icone";

const ESTADOS: Record<
  Exclude<EstadoDoRegistro, "sem_status">,
  { texto: string; icone: NomeDoIcone; classes: string }
> = {
  conforme: {
    texto: "Conforme",
    icone: "ok",
    classes: "border-sucesso-300 bg-sucesso-50 text-sucesso-700",
  },
  nao_conforme: {
    texto: "Não conforme",
    icone: "fechar",
    classes: "border-erro-300 bg-erro-50 text-erro-700",
  },
  erro: {
    texto: "Erro no cálculo",
    icone: "alerta",
    classes: "border-aviso-300 bg-aviso-50 text-aviso-700",
  },
  aguardando: {
    texto: "Aguardando dados",
    icone: "historico",
    classes: "border-pedra-300 bg-pedra-100 text-pedra-700",
  },
};

export const ROTULOS_DE_ESTADO: Record<string, string> = Object.fromEntries(
  Object.entries(ESTADOS).map(([id, e]) => [id, e.texto]),
);

/**
 * O estado do resultado de um registro. Sempre com ícone **e** texto: a cor sozinha não pode
 * carregar o significado (AGENTS.md §2.11). Quem decide o estado é o servidor (§7).
 */
export function SeloDeEstado({ estado }: { estado: EstadoDoRegistro | null | undefined }) {
  if (!estado || estado === "sem_status") return null;
  const { texto, icone, classes } = ESTADOS[estado];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-controle border px-1.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      <Icone nome={icone} tamanho={12} />
      {texto}
    </span>
  );
}
