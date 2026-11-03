import type { Celula } from "../../lib/celulas";
import { Conformidade, Icone } from "../../ui";

/**
 * O que mostrar de um registro de origem: o que ele libera para os dependentes (os campos
 * compartilhados) e, se não libera nada, os primeiros campos.
 */
export function escolherCelulas(celulas: Celula[], limite: number): Celula[] {
  const liberadas = celulas.filter((celula) => celula.compartilhado);
  return (liberadas.length > 0 ? liberadas : celulas).slice(0, limite);
}

/** Pares rótulo → valor, com a unidade em separado e a conformidade como selo. */
export function ResumoDeRegistro({ celulas }: { celulas: Celula[] }) {
  if (celulas.length === 0) return <p className="text-sm text-pedra-500">Sem valores a mostrar.</p>;
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
      {celulas.map((celula) => (
        <div key={celula.id} className="flex items-baseline justify-between gap-3 text-sm">
          <dt className="flex min-w-0 items-center gap-1.5 text-pedra-600">
            {celula.compartilhado ? (
              <Icone
                nome="elo"
                tamanho={12}
                className="shrink-0 text-sinal-600"
                role="img"
                aria-label="Compartilhado"
              />
            ) : null}
            <span className="truncate">{celula.rotulo}</span>
          </dt>
          <dd className="shrink-0 font-mono tabular-nums">
            {celula.conforme !== null ? (
              <Conformidade conforme={celula.conforme} texto={celula.texto} />
            ) : (
              <>
                {celula.texto === "" ? "—" : celula.texto}
                {celula.unidade ? (
                  <span className="ml-1 text-xs text-pedra-500">{celula.unidade}</span>
                ) : null}
              </>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
