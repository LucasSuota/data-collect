import { useEffect, useState } from "react";
import type { ResumoDeFormulario } from "../api/cliente";
import { useApi } from "../api/contexto";
import { CampoDeBusca, Esqueleto, EstadoVazio, Gaveta, Icone } from "../ui";

/** "Novo registro": escolhe o formulário que será preenchido (folha de baixo no celular). */
export function SeletorDeFormulario({
  aoEscolher,
  aoFechar,
}: {
  aoEscolher: (formularioId: number) => void;
  aoFechar: () => void;
}) {
  const api = useApi();
  const [formularios, setFormularios] = useState<ResumoDeFormulario[] | null>(null);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    let ativo = true;
    void api.listarFormularios().then((lista) => ativo && setFormularios(lista));
    return () => {
      ativo = false;
    };
  }, [api]);

  const visiveis = (formularios ?? []).filter((f) =>
    f.nome.toLowerCase().includes(busca.trim().toLowerCase()),
  );

  return (
    <Gaveta
      titulo="Novo registro"
      subtitulo="Qual formulário você vai preencher?"
      aoFechar={aoFechar}
      fecharAoClicarFora
    >
      <div className="flex flex-col gap-3 p-4">
        <CampoDeBusca
          rotulo="Buscar formulário"
          placeholder="Buscar formulário"
          valor={busca}
          aoMudar={setBusca}
        />
        {formularios === null ? (
          <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
            <Esqueleto className="h-12" />
            <Esqueleto className="h-12" />
            <Esqueleto className="h-12" />
          </div>
        ) : visiveis.length === 0 ? (
          <EstadoVazio icone="documento" titulo="Nenhum formulário encontrado">
            Crie um formulário primeiro, ou importe um exemplo na galeria.
          </EstadoVazio>
        ) : (
          <ul className="flex flex-col gap-2">
            {visiveis.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => aoEscolher(f.id)}
                  className="flex min-h-12 w-full items-center justify-between gap-2 rounded-cartao border border-pedra-200 bg-superficie px-4 py-2 text-left font-medium hover:border-sinal-300"
                >
                  {f.nome}
                  <Icone nome="seta" className="text-pedra-400" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Gaveta>
  );
}
