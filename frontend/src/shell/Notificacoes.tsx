import { useCallback, useEffect, useRef, useState } from "react";
import type { Notificacao, Notificacoes as Lista } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Icone } from "../ui";

/** Só dentro do app, sem push nem e-mail (AGENTS.md §2.18). */
export function textoDaNotificacao(n: Notificacao): string {
  const ref = n.referencia as Record<string, unknown>;
  const texto = (chave: string) => (typeof ref[chave] === "string" ? String(ref[chave]) : null);
  switch (n.tipo) {
    case "convite_aceito":
      return `${texto("pessoa") ?? "Alguém"} aceitou o convite e entrou na equipe.`;
    case "cargo_alterado":
      return `Seu cargo mudou${texto("cargo") ? ` para ${texto("cargo")}` : ""}.`;
    case "registro_editado":
      return `${texto("pessoa") ?? "Outra pessoa"} editou um registro seu${ref["registro_id"] ? ` (#${String(ref["registro_id"])})` : ""}.`;
    case "erro_em_cascata":
      return `Um cálculo deu erro em um registro seu${ref["registro_id"] ? ` (#${String(ref["registro_id"])})` : ""} depois de uma alteração na origem.`;
  }
}

export function SinoDeNotificacoes() {
  const api = useApi();
  const [lista, setLista] = useState<Lista | null>(null);
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);

  const carregar = useCallback(() => {
    api.notificacoes().then(setLista, () => undefined); // aviso é conveniência: falhar não atrapalha
  }, [api]);

  useEffect(() => {
    carregar();
    const intervalo = window.setInterval(carregar, 60_000);
    return () => window.clearInterval(intervalo);
  }, [carregar]);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => {
      if (raiz.current && !raiz.current.contains(e.target as Node)) setAberto(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [aberto]);

  async function marcar(n: Notificacao) {
    await api.marcarNotificacaoLida(n.id);
    carregar();
  }

  const naoLidas = lista?.nao_lidas ?? 0;
  return (
    <div ref={raiz} className="relative">
      <button
        type="button"
        aria-label={naoLidas > 0 ? `Notificações, ${naoLidas} não lidas` : "Notificações"}
        aria-expanded={aberto}
        onClick={() => setAberto((v) => !v)}
        className="relative grid size-11 place-items-center rounded-controle border border-pedra-200 bg-superficie text-pedra-700 hover:bg-pedra-100"
      >
        <Icone nome="sino" tamanho={20} />
        {naoLidas > 0 ? (
          <span className="absolute top-1.5 right-1.5 grid min-w-4 place-items-center rounded-full bg-sinal-500 px-1 text-[0.625rem] font-semibold text-superficie">
            {naoLidas}
          </span>
        ) : null}
      </button>
      {aberto ? (
        <div
          role="dialog"
          aria-label="Notificações"
          className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-cartao border border-pedra-200 bg-superficie p-2 shadow-elevada"
        >
          {lista && lista.itens.length > 0 ? (
            <ul className="flex max-h-96 flex-col overflow-y-auto">
              {lista.itens.map((n) => (
                <li key={n.id} className="flex items-start gap-2 rounded-controle p-2 text-sm">
                  <span className={n.lida ? "flex-1 text-pedra-500" : "flex-1 font-medium"}>
                    {textoDaNotificacao(n)}
                  </span>
                  {!n.lida ? (
                    <button
                      type="button"
                      onClick={() => void marcar(n)}
                      className="min-h-9 shrink-0 rounded-controle px-2 text-xs text-sinal-500 hover:bg-sinal-100"
                    >
                      Marcar como lida
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-3 text-sm text-pedra-600">Nada de novo por aqui.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
