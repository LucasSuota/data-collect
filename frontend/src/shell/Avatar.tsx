/** Iniciais num círculo: a pessoa logada em preto, as demais em tons do azul (design de referência). */
export function Avatar({
  nome,
  tamanho = 40,
  escuro = false,
}: {
  nome: string;
  tamanho?: number;
  escuro?: boolean;
}) {
  const partes = nome.trim().split(/\s+/);
  const iniciais = (
    (partes[0]?.[0] ?? "?") + (partes.length > 1 ? (partes[partes.length - 1]?.[0] ?? "") : "")
  ).toUpperCase();
  return (
    <span
      aria-hidden="true"
      style={{ width: tamanho, height: tamanho, fontSize: tamanho * 0.36 }}
      className={`grid shrink-0 place-items-center rounded-full font-semibold ${escuro ? "bg-pedra-900 text-superficie" : "bg-sinal-100 text-sinal-600"}`}
    >
      {iniciais}
    </span>
  );
}
