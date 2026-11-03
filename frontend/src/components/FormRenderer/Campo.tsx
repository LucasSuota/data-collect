import type { ReactNode } from "react";

interface Props {
  /** O `id` do campo na definição: ancora o rótulo, o erro e os testes. */
  id: string;
  rotulo: string;
  unidade?: string | null;
  obrigatorio?: boolean | null;
  erros?: string[];
  children: (propsDoControle: PropsDoControle) => ReactNode;
}

export interface PropsDoControle {
  id: string;
  "aria-invalid": boolean;
  "aria-describedby": string | undefined;
  "aria-required": boolean;
}

/** Moldura de um campo: rótulo, controle e as mensagens de erro no lugar certo. */
export function Campo({ id, rotulo, unidade, obrigatorio, erros = [], children }: Props) {
  const idDoControle = `campo-${id}`;
  const idDosErros = `erros-${id}`;
  return (
    <div className="flex flex-col gap-1" data-campo={id}>
      <label htmlFor={idDoControle} className="text-sm font-medium text-pedra-700">
        {rotulo}
        {unidade ? <span className="ml-1 font-normal text-pedra-500">({unidade})</span> : null}
        {obrigatorio ? (
          <span className="ml-1 text-red-600" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children({
        id: idDoControle,
        "aria-invalid": erros.length > 0,
        "aria-describedby": erros.length > 0 ? idDosErros : undefined,
        "aria-required": Boolean(obrigatorio),
      })}
      {erros.length > 0 ? (
        <ul id={idDosErros} role="alert" className="text-sm text-red-700">
          {erros.map((mensagem) => (
            <li key={mensagem}>{mensagem}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export const CLASSE_DO_CONTROLE =
  "rounded border border-pedra-300 bg-white px-2 py-1.5 text-pedra-900 " +
  "aria-[invalid=true]:border-red-500 disabled:bg-pedra-100";
