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
      <label
        id={`rotulo-${id}`}
        htmlFor={idDoControle}
        className="text-sm font-medium text-pedra-800"
      >
        {rotulo}
        {unidade ? <span className="ml-1 font-normal text-pedra-500">({unidade})</span> : null}
        {obrigatorio ? (
          <span className="ml-1 text-erro-700" aria-hidden="true">
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
        <ul id={idDosErros} role="alert" className="text-sm text-erro-700">
          {erros.map((mensagem) => (
            <li key={mensagem}>{mensagem}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export const CLASSE_DO_CONTROLE =
  "min-h-9 rounded-controle border border-pedra-300 bg-superficie px-3 text-sm text-pedra-900 " +
  "placeholder:text-pedra-400 transition-colors duration-(--duracao-rapida) hover:border-pedra-400 " +
  "aria-[invalid=true]:border-erro-300 aria-[invalid=true]:bg-erro-50 " +
  "disabled:border-pedra-200 disabled:bg-pedra-100 disabled:text-pedra-600 disabled:hover:border-pedra-200";
