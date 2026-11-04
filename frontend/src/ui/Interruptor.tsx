/** Liga/desliga acessível (`role="switch"`), com o rótulo e a descrição lidos juntos. */
export function Interruptor({
  ligado,
  aoMudar,
  rotulo,
  descricao,
  desabilitado = false,
}: {
  ligado: boolean;
  aoMudar: (valor: boolean) => void;
  rotulo: string;
  descricao?: string;
  desabilitado?: boolean;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-b border-pedra-100 py-2 last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-semibold">{rotulo}</p>
        {descricao ? <p className="text-xs text-pedra-600">{descricao}</p> : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={ligado}
        aria-label={rotulo}
        disabled={desabilitado}
        onClick={() => aoMudar(!ligado)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-(--duracao-rapida) disabled:opacity-50 ${ligado ? "bg-sinal-500" : "bg-pedra-500"}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 size-6 rounded-full bg-superficie shadow transition-transform duration-(--duracao-rapida) ${ligado ? "translate-x-5" : ""}`}
        />
      </button>
    </div>
  );
}
