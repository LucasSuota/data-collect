import { Construtor } from "./construtor/Construtor";
import { PaginaCriarComIa } from "./ia/PaginaCriarComIa";
import { PaginaDoMapa } from "./mapa/PaginaDoMapa";
import { ProvedorDeGavetas } from "./registros/ProvedorDeGavetas";
import { useRota } from "./rotas";
import { PaginaDeFormularios } from "./paginas/PaginaDeFormularios";
import { PaginaDeRegistro } from "./paginas/PaginaDeRegistro";
import { PaginaDeRegistros } from "./paginas/PaginaDeRegistros";

/** Uma ficha: quatro linhas de campo, a primeira em destaque. */
function Marca() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="3" y="3" width="18" height="18" rx="4" fill="var(--color-pedra-900)" />
      <rect x="7" y="7" width="10" height="2" rx="1" fill="var(--color-sinal-500)" />
      <rect x="7" y="11" width="10" height="2" rx="1" fill="var(--color-superficie)" />
      <rect x="7" y="15" width="6" height="2" rx="1" fill="var(--color-superficie)" />
    </svg>
  );
}

function LinkDoMenu({
  href,
  ativo,
  children,
}: {
  href: string;
  ativo: boolean;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      aria-current={ativo ? "page" : undefined}
      className={`rounded-controle px-2.5 py-1.5 font-medium transition-colors duration-(--duracao-rapida) ${ativo ? "bg-pedra-100 text-pedra-900" : "text-pedra-600 hover:text-pedra-900"}`}
    >
      {children}
    </a>
  );
}

export function App() {
  const [rota, navegar] = useRota();

  return (
    <ProvedorDeGavetas>
      <div className="min-h-screen">
        <header className="border-b border-pedra-200 bg-superficie">
          <nav className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-3.5">
            <a href="#/" className="flex items-center gap-2.5 rounded-controle">
              <Marca />
              <span className="text-[0.9375rem] font-semibold tracking-tight">data-collect</span>
            </a>
            <div className="ml-6 flex items-center gap-1 text-sm">
              <LinkDoMenu href="#/" ativo={rota.nome !== "mapa"}>
                Formulários
              </LinkDoMenu>
              <LinkDoMenu href="#/mapa" ativo={rota.nome === "mapa"}>
                Mapa
              </LinkDoMenu>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">
          {rota.nome === "formularios" ? <PaginaDeFormularios navegar={navegar} /> : null}
          {rota.nome === "mapa" ? <PaginaDoMapa navegar={navegar} /> : null}
          {rota.nome === "pasta" ? (
            <PaginaDeFormularios navegar={navegar} pastaId={rota.pastaId} />
          ) : null}
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
            <Construtor modo={{ tipo: "novo", pastaId: rota.pastaId }} navegar={navegar} />
          ) : null}
          {rota.nome === "criarComIa" ? <PaginaCriarComIa navegar={navegar} /> : null}
          {rota.nome === "editarFormulario" ? (
            <Construtor
              modo={{ tipo: "editar", formularioId: rota.formularioId }}
              navegar={navegar}
            />
          ) : null}
          {rota.nome === "naoEncontrada" ? (
            <p>
              Página não encontrada.{" "}
              <a href="#/" className="underline decoration-sinal-500 underline-offset-2">
                Voltar aos formulários
              </a>
              .
            </p>
          ) : null}
        </main>
      </div>
    </ProvedorDeGavetas>
  );
}
