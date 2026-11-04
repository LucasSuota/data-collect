import { useEffect, useState } from "react";
import type { RegistroRecente, ResumoDeFormulario } from "../api/cliente";
import { useApi } from "../api/contexto";
import { Esqueleto, EstadoVazio, Icone } from "../ui";
import { LinhaDeRegistro } from "./PaginaInicio";

/** "Registros" no menu: os mais recentes de todos os formulários e a porta para cada formulário. */
export function PaginaDeRegistrosRecentes() {
  const api = useApi();
  const [recentes, setRecentes] = useState<RegistroRecente[] | null>(null);
  const [formularios, setFormularios] = useState<ResumoDeFormulario[]>([]);

  useEffect(() => {
    let ativo = true;
    void api.registrosRecentes(30).then(
      (r) => ativo && setRecentes(r),
      () => ativo && setRecentes([]),
    );
    void api.listarFormularios().then(
      (f) => ativo && setFormularios(f),
      () => undefined,
    );
    return () => {
      ativo = false;
    };
  }, [api]);

  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <h1 className="text-3xl font-extrabold">Registros</h1>
      {formularios.length > 0 ? (
        <section aria-labelledby="por-formulario" className="flex flex-col gap-2">
          <h2
            id="por-formulario"
            className="text-sm font-semibold tracking-wider text-pedra-500 uppercase"
          >
            Por formulário
          </h2>
          <ul className="flex flex-wrap gap-2">
            {formularios.map((f) => (
              <li key={f.id}>
                <a
                  href={`#/formularios/${f.id}/registros`}
                  className="inline-flex min-h-11 items-center gap-2 rounded-cartao bg-pedra-100 px-4 text-sm font-medium hover:bg-pedra-200"
                >
                  <Icone nome="registros" tamanho={16} /> {f.nome}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <section aria-labelledby="recentes-todos" className="flex flex-col gap-2">
        <h2
          id="recentes-todos"
          className="text-sm font-semibold tracking-wider text-pedra-500 uppercase"
        >
          Mais recentes
        </h2>
        {recentes === null ? (
          <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
            <Esqueleto className="h-16 rounded-cartao" />
            <Esqueleto className="h-16 rounded-cartao" />
          </div>
        ) : recentes.length === 0 ? (
          <EstadoVazio icone="registros" titulo="Nenhum registro ainda">
            Escolha um formulário e preencha o primeiro registro.
          </EstadoVazio>
        ) : (
          <ul className="flex flex-col gap-2">
            {recentes.map((r) => (
              <li key={r.id}>
                <LinhaDeRegistro r={r} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
