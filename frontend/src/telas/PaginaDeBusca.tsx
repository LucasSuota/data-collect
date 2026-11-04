import { useEffect, useState } from "react";
import type { Busca } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Esqueleto, EstadoVazio, Icone } from "../ui";

export function PaginaDeBusca({ termo }: { termo: string }) {
  const api = useApi();
  const [resultado, setResultado] = useState<Busca | null>(null);

  useEffect(() => {
    let ativo = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- recomeça a busca a cada termo
    setResultado(null);
    void api.buscar(termo).then(
      (r) => ativo && setResultado(r),
      () => ativo && setResultado({ formularios: [], registros: [] }),
    );
    return () => {
      ativo = false;
    };
  }, [api, termo]);

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-2xl font-extrabold">Resultados para “{termo}”</h1>
      {resultado === null ? (
        <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
          <Esqueleto className="h-14 rounded-cartao" />
          <Esqueleto className="h-14 rounded-cartao" />
        </div>
      ) : resultado.formularios.length + resultado.registros.length === 0 ? (
        <EstadoVazio icone="busca" titulo="Nada encontrado">
          Tente o nome de um formulário, o número de um registro (#12) ou um valor de texto.
        </EstadoVazio>
      ) : (
        <>
          {resultado.formularios.length > 0 ? (
            <section aria-labelledby="b-formularios" className="flex flex-col gap-2">
              <h2
                id="b-formularios"
                className="text-sm font-semibold tracking-wider text-pedra-500 uppercase"
              >
                Formulários
              </h2>
              {resultado.formularios.map((f) => (
                <a
                  key={f.id}
                  href={`#/formularios/${f.id}/registros`}
                  className="flex min-h-12 items-center gap-2 rounded-cartao border border-pedra-200 bg-superficie px-4 font-semibold"
                >
                  <Icone nome="documento" /> {f.nome}
                </a>
              ))}
            </section>
          ) : null}
          {resultado.registros.length > 0 ? (
            <section aria-labelledby="b-registros" className="flex flex-col gap-2">
              <h2
                id="b-registros"
                className="text-sm font-semibold tracking-wider text-pedra-500 uppercase"
              >
                Registros
              </h2>
              {resultado.registros.map((r) => (
                <a
                  key={r.id}
                  href={`#/registros/${r.id}`}
                  className="flex min-h-12 items-center justify-between gap-2 rounded-cartao border border-pedra-200 bg-superficie px-4"
                >
                  <span className="font-semibold">{r.formulario}</span>
                  <span className="font-mono text-sm text-pedra-600">#{r.id}</span>
                </a>
              ))}
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
