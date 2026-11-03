import { Icone } from "./Icone";

/** Verde ou vermelho, sempre com ícone e texto: a cor sozinha não pode carregar o significado. */
export function Conformidade({ conforme, texto }: { conforme: boolean; texto: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-controle border px-1.5 py-0.5 text-xs font-medium ${conforme ? "border-sucesso-300 bg-sucesso-50 text-sucesso-700" : "border-erro-300 bg-erro-50 text-erro-700"}`}
    >
      <Icone nome={conforme ? "ok" : "alerta"} tamanho={12} />
      {texto}
    </span>
  );
}
