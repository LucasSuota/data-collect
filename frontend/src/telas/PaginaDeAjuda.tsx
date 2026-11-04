import { useEffect, useState } from "react";
import type { Guia } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Markdown } from "../lib/Markdown";
import { Botao, Esqueleto, Icone } from "../ui";

/** Central de ajuda: os guias em Markdown vêm do servidor (a mesma pasta alimenta o chatbot). */
export function PaginaDeAjuda({ guiaId }: { guiaId?: string }) {
  const api = useApi();
  const [guias, setGuias] = useState<Guia[] | null>(null);

  useEffect(() => {
    let ativo = true;
    void api.guias().then(
      (r) => ativo && setGuias(r.guias),
      () => ativo && setGuias([]),
    );
    return () => {
      ativo = false;
    };
  }, [api]);

  if (guias === null) {
    return (
      <div role="status" aria-label="Carregando" className="flex flex-col gap-3">
        <Esqueleto className="h-9 w-64" />
        <Esqueleto className="h-14 rounded-cartao" />
        <Esqueleto className="h-14 rounded-cartao" />
      </div>
    );
  }
  const guia = guiaId ? guias.find((g) => g.id === guiaId) : undefined;

  if (guia) {
    return (
      <article className="flex max-w-2xl flex-col gap-4">
        <a
          href="#/ajuda"
          className="inline-flex min-h-11 w-fit items-center gap-1 text-sm font-semibold text-sinal-500"
        >
          <Icone nome="voltar" /> Central de ajuda
        </a>
        <Markdown texto={guia.markdown} />
      </article>
    );
  }
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-3xl font-extrabold">Central de ajuda</h1>
      {guiaId ? <p role="alert">Guia não encontrado.</p> : null}
      <ul className="flex flex-col gap-2">
        {guias.map((g) => (
          <li key={g.id}>
            <a
              href={`#/ajuda/${encodeURIComponent(g.id)}`}
              className="flex min-h-14 items-center justify-between rounded-cartao border border-pedra-200 bg-superficie px-4 font-semibold shadow-cartao hover:border-sinal-300"
            >
              {g.titulo}
              <Icone nome="seta" className="text-pedra-400" />
            </a>
          </li>
        ))}
      </ul>
      <Botao
        className="w-fit"
        onClick={() => {
          void api
            .progresso()
            .then((p) =>
              api.salvarProgresso({
                ...p,
                tour_concluido: false,
                passo: 0,
                checklist_dispensado: false,
              }),
            )
            .then(() => {
              window.location.hash = "#/";
            });
        }}
      >
        Rever o passeio do primeiro acesso
      </Botao>
    </div>
  );
}
