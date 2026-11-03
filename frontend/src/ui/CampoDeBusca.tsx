import { useId, type InputHTMLAttributes } from "react";
import { Icone } from "./Icone";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "value" | "onChange"> {
  /** O rótulo fica só para o leitor de tela: o ícone e o texto de exemplo já explicam a quem vê. */
  rotulo: string;
  valor: string;
  aoMudar: (valor: string) => void;
}

/** Campo de busca com lupa e botão de limpar. Esc também limpa. */
export function CampoDeBusca({ rotulo, valor, aoMudar, className = "", ...resto }: Props) {
  const id = useId();
  return (
    <div className={`relative ${className}`}>
      <label htmlFor={id} className="sr-only">
        {rotulo}
      </label>
      <Icone
        nome="busca"
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-pedra-400"
      />
      <input
        {...resto}
        id={id}
        type="search"
        autoComplete="off"
        value={valor}
        onChange={(evento) => aoMudar(evento.target.value)}
        onKeyDown={(evento) => {
          resto.onKeyDown?.(evento);
          if (evento.key === "Escape" && valor !== "") {
            evento.preventDefault();
            aoMudar("");
          }
        }}
        className="min-h-9 w-full rounded-controle border border-pedra-300 bg-superficie pr-8 pl-9 text-sm text-pedra-900 transition-colors duration-(--duracao-rapida) placeholder:text-pedra-400 hover:border-pedra-400 [&::-webkit-search-cancel-button]:appearance-none"
      />
      {valor !== "" ? (
        <button
          type="button"
          aria-label="Limpar o texto"
          className="absolute top-1/2 right-1.5 grid size-6 -translate-y-1/2 place-items-center rounded-controle text-pedra-500 hover:bg-pedra-200 hover:text-pedra-800"
          onClick={() => aoMudar("")}
        >
          <Icone nome="fechar" tamanho={14} />
        </button>
      ) : null}
    </div>
  );
}
