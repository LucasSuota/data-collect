import { lazy, Suspense } from "react";
import { TelaDeCarregamento } from "./auth/telas";
import { ProvedorDeGavetas } from "./registros/ProvedorDeGavetas";
import { useRota } from "./rotas";
import { Shell } from "./shell/Shell";
import { PaginaDeFormularios } from "./paginas/PaginaDeFormularios";
import { PaginaDeRegistro } from "./paginas/PaginaDeRegistro";
import { PaginaDeRegistros } from "./paginas/PaginaDeRegistros";
import { PaginaDeBusca } from "./telas/PaginaDeBusca";
import { PaginaDeExemplos } from "./telas/PaginaDeExemplos";
import { PaginaDePerfil } from "./telas/PaginaDePerfil";
import { PaginaDeRegistrosRecentes } from "./telas/PaginaDeRegistrosRecentes";
import { PaginaInicio } from "./telas/PaginaInicio";

const Construtor = lazy(() =>
  import("./construtor/Construtor").then((m) => ({ default: m.Construtor })),
);
const PaginaCriarComIa = lazy(() =>
  import("./ia/PaginaCriarComIa").then((m) => ({ default: m.PaginaCriarComIa })),
);
const PaginaDoMapa = lazy(() =>
  import("./mapa/PaginaDoMapa").then((m) => ({ default: m.PaginaDoMapa })),
);
const PaginaDaEquipe = lazy(() =>
  import("./telas/PaginaDaEquipe").then((m) => ({ default: m.PaginaDaEquipe })),
);
const PaginaDaIa = lazy(() =>
  import("./telas/PaginaDaIa").then((m) => ({ default: m.PaginaDaIa })),
);
const PaginaDeCargos = lazy(() =>
  import("./telas/PaginaDeCargos").then((m) => ({ default: m.PaginaDeCargos })),
);
const PaginaDoChat = lazy(() =>
  import("./telas/PaginaDoChat").then((m) => ({ default: m.PaginaDoChat })),
);
const PaginaDeAjuda = lazy(() =>
  import("./telas/PaginaDeAjuda").then((m) => ({ default: m.PaginaDeAjuda })),
);

/** Troca a tela pela rota. Já roda dentro de uma sessão iniciada (ver `auth/Autenticacao`). */
export function App() {
  const [rota, navegar] = useRota();

  return (
    <ProvedorDeGavetas>
      <Shell rota={rota} navegar={navegar}>
        <Suspense fallback={<TelaDeCarregamento />}>
          {rota.nome === "inicio" ? <PaginaInicio navegar={navegar} /> : null}
          {rota.nome === "formularios" ? <PaginaDeFormularios navegar={navegar} /> : null}
          {rota.nome === "pasta" ? (
            <PaginaDeFormularios navegar={navegar} pastaId={rota.pastaId} />
          ) : null}
          {rota.nome === "mapa" ? <PaginaDoMapa navegar={navegar} /> : null}
          {rota.nome === "registrosRecentes" ? <PaginaDeRegistrosRecentes /> : null}
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
          {rota.nome === "editarFormulario" ? (
            <Construtor
              modo={{ tipo: "editar", formularioId: rota.formularioId }}
              navegar={navegar}
            />
          ) : null}
          {rota.nome === "criarComIa" ? <PaginaCriarComIa navegar={navegar} /> : null}
          {rota.nome === "equipe" ? <PaginaDaEquipe /> : null}
          {rota.nome === "cargos" ? <PaginaDeCargos /> : null}
          {rota.nome === "ia" ? <PaginaDaIa /> : null}
          {rota.nome === "chat" ? <PaginaDoChat /> : null}
          {rota.nome === "ajuda" ? <PaginaDeAjuda guiaId={rota.guia} /> : null}
          {rota.nome === "perfil" ? <PaginaDePerfil /> : null}
          {rota.nome === "exemplos" ? <PaginaDeExemplos navegar={navegar} /> : null}
          {rota.nome === "busca" ? <PaginaDeBusca termo={rota.termo} /> : null}
          {rota.nome === "termos" || rota.nome === "privacidade" || rota.nome === "convite" ? (
            <p>
              <a href="#/" className="text-sinal-500 underline underline-offset-2">
                Voltar ao início
              </a>
            </p>
          ) : null}
          {rota.nome === "naoEncontrada" ? (
            <p>
              Página não encontrada.{" "}
              <a href="#/" className="text-sinal-500 underline underline-offset-2">
                Voltar ao início
              </a>
              .
            </p>
          ) : null}
        </Suspense>
      </Shell>
    </ProvedorDeGavetas>
  );
}
