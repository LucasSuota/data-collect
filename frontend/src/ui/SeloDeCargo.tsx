/** O cargo como etiqueta: Administrador em preto, os demais em tons de azul (design de referência). */
export function SeloDeCargo({ nome }: { nome: string }) {
  const admin = nome === "Administrador";
  return (
    <span
      className={`inline-flex items-center rounded-controle px-1.5 py-0.5 text-xs font-semibold ${admin ? "bg-pedra-900 text-superficie" : "bg-sinal-100 text-sinal-600"}`}
    >
      {nome}
    </span>
  );
}
