import { useId, type InputHTMLAttributes } from "react";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  rotulo: string;
  /** Mensagens do servidor para este campo, já em português. */
  erros?: string[];
  dica?: string;
}

/** Rótulo, campo, dica e erro ligados por `id` (o leitor de tela lê tudo junto). */
export function CampoDeTexto({ rotulo, erros = [], dica, className = "", ...resto }: Props) {
  const id = useId();
  const idDoErro = `${id}-erro`;
  const idDaDica = `${id}-dica`;
  const invalido = erros.length > 0;
  const descricao = [invalido ? idDoErro : null, dica ? idDaDica : null].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-pedra-800">
        {rotulo}
      </label>
      <input
        {...resto}
        id={id}
        aria-invalid={invalido}
        aria-describedby={descricao || undefined}
        className={[
          "min-h-11 rounded-controle border bg-superficie px-3 text-sm text-pedra-900",
          "placeholder:text-pedra-400 transition-colors duration-(--duracao-rapida)",
          invalido ? "border-erro-300" : "border-pedra-300 hover:border-pedra-400",
          className,
        ].join(" ")}
      />
      {invalido ? (
        <p id={idDoErro} className="text-sm text-erro-700">
          {erros.join(" ")}
        </p>
      ) : null}
      {dica ? (
        <p id={idDaDica} className="text-sm text-pedra-500">
          {dica}
        </p>
      ) : null}
    </div>
  );
}
