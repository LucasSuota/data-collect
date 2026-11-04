import { useState } from "react";
import { CampoDeBusca } from "../ui";

/** A busca é determinística (sem IA): ao enviar, abre a tela de resultados. */
export function BuscaGlobal({
  aoBuscar,
  className = "",
}: {
  aoBuscar: (termo: string) => void;
  className?: string;
}) {
  const [termo, setTermo] = useState("");
  return (
    <form
      role="search"
      className={className}
      onSubmit={(e) => {
        e.preventDefault();
        if (termo.trim()) aoBuscar(termo.trim());
      }}
    >
      <CampoDeBusca
        rotulo="Buscar formulário ou registro"
        placeholder="Buscar formulário ou registro"
        valor={termo}
        aoMudar={setTermo}
      />
    </form>
  );
}
