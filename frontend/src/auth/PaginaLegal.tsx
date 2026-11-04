import { useEffect, useState } from "react";
import type { DocumentoLegal } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Markdown } from "../lib/Markdown";
import { Esqueleto, Marca } from "../ui";

/** Termos e Política: públicos, abrem antes do login (AGENTS.md §2.15). */
export function PaginaLegal({ documento }: { documento: "termos" | "privacidade" }) {
  const api = useApi();
  const [texto, setTexto] = useState<DocumentoLegal | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let ativo = true;
    api
      .documentosLegais()
      .then((r) => {
        if (ativo) setTexto(r.documentos.find((d) => d.id === documento) ?? null);
      })
      .catch(() => ativo && setFalhou(true));
    return () => {
      ativo = false;
    };
  }, [api, documento]);

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-8">
      <a href="#/" className="w-fit">
        <Marca className="text-xl" />
      </a>
      {falhou ? <p role="alert">Não foi possível carregar o documento agora.</p> : null}
      {!texto && !falhou ? (
        <div role="status" aria-label="Carregando" className="flex flex-col gap-3">
          <Esqueleto className="h-8 w-64" />
          <Esqueleto className="h-4 w-full" />
          <Esqueleto className="h-4 w-5/6" />
        </div>
      ) : null}
      {texto ? (
        <>
          <p className="font-mono text-xs text-pedra-500">Versão {texto.versao}</p>
          <Markdown texto={texto.markdown} />
        </>
      ) : null}
    </main>
  );
}
