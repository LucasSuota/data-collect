import { Construtor } from "./construtor/Construtor";
import { useRota } from "./rotas";
import { PaginaDeFormularios } from "./paginas/PaginaDeFormularios";
import { PaginaDeRegistro } from "./paginas/PaginaDeRegistro";
import { PaginaDeRegistros } from "./paginas/PaginaDeRegistros";

export function App() {
  const [rota, navegar] = useRota();

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b border-slate-200">
        <nav className="mx-auto flex max-w-5xl items-center gap-4 p-4">
          <a href="#/" className="text-lg font-semibold">
            Construtor de Formulários
          </a>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl p-4">
        {rota.nome === "formularios" ? <PaginaDeFormularios navegar={navegar} /> : null}
        {rota.nome === "registros" ? (
          <PaginaDeRegistros formularioId={rota.formularioId} navegar={navegar} />
        ) : null}
        {rota.nome === "novoRegistro" ? (
          <PaginaDeRegistro
            modo={{ tipo: "novo", formularioId: rota.formularioId }}
            navegar={navegar}
          />
        ) : null}
        {rota.nome === "registro" ? (
          <PaginaDeRegistro
            modo={{ tipo: "editar", registroId: rota.registroId }}
            navegar={navegar}
          />
        ) : null}
        {rota.nome === "novoFormulario" ? (
          <Construtor modo={{ tipo: "novo" }} navegar={navegar} />
        ) : null}
        {rota.nome === "editarFormulario" ? (
          <Construtor
            modo={{ tipo: "editar", formularioId: rota.formularioId }}
            navegar={navegar}
          />
        ) : null}
        {rota.nome === "naoEncontrada" ? (
          <p>
            Página não encontrada.{" "}
            <a href="#/" className="underline">
              Voltar aos formulários
            </a>
            .
          </p>
        ) : null}
      </main>
    </div>
  );
}
