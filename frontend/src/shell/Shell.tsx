import { useState, type ReactNode } from "react";
import { useSessao } from "../auth/sessao";
import { caminhoDe, type Rota } from "../rotas";
import { Icone, Marca } from "../ui";
import { Avatar } from "./Avatar";
import { BuscaGlobal } from "./BuscaGlobal";
import { barraInferior, itemAtual, itensVisiveis, type ItemDeNavegacao } from "./navegacao";
import { SinoDeNotificacoes } from "./Notificacoes";
import { SeletorDeFormulario } from "./SeletorDeFormulario";

function LinkLateral({ item, ativo }: { item: ItemDeNavegacao; ativo: boolean }) {
  return (
    <a
      href={caminhoDe(item.destino)}
      aria-current={ativo ? "page" : undefined}
      className={`flex min-h-11 items-center gap-2.5 rounded-controle px-3 text-sm font-medium transition-colors duration-(--duracao-rapida) ${ativo ? "bg-sinal-100 text-sinal-600" : "text-pedra-700 hover:bg-pedra-100"}`}
    >
      <Icone nome={item.icone} tamanho={18} />
      {item.rotulo}
    </a>
  );
}

function MenuLateral({ rota, itens }: { rota: Rota; itens: ItemDeNavegacao[] }) {
  const sessao = useSessao();
  const atual = itemAtual(itens, rota);
  const grupos: [string, ItemDeNavegacao[]][] = [
    ["Trabalho", itens.filter((i) => i.grupo === "trabalho")],
    ["Administração", itens.filter((i) => i.grupo === "administracao")],
  ];
  return (
    <aside className="sticky top-0 hidden h-dvh w-64 shrink-0 flex-col gap-6 border-r border-pedra-200 bg-superficie px-3 py-5 sm:flex">
      <a href="#/" className="px-3">
        <Marca className="text-xl" />
      </a>
      <nav aria-label="Principal" className="flex flex-1 flex-col gap-6 overflow-y-auto">
        {grupos.map(([titulo, lista]) =>
          lista.length > 0 ? (
            <div key={titulo} className="flex flex-col gap-1">
              <p className="px-3 pb-1 text-[0.6875rem] font-semibold tracking-wider text-pedra-500 uppercase">
                {titulo}
              </p>
              {lista.map((item) => (
                <LinkLateral key={item.id} item={item} ativo={atual?.id === item.id} />
              ))}
            </div>
          ) : null,
        )}
      </nav>
      <div className="flex flex-col gap-1">
        <a
          href="#/ajuda"
          aria-current={rota.nome === "ajuda" ? "page" : undefined}
          className="flex min-h-11 items-center gap-2.5 rounded-controle px-3 text-sm font-medium text-pedra-700 hover:bg-pedra-100"
        >
          <Icone nome="ajuda" tamanho={18} />
          Ajuda
        </a>
        <a
          href="#/perfil"
          className="flex min-h-12 items-center gap-2.5 rounded-controle bg-pedra-100 px-3 hover:bg-pedra-200"
        >
          <Avatar nome={sessao.eu.pessoa.nome} tamanho={32} escuro />
          <span className="min-w-0 text-left">
            <span className="block truncate text-sm font-semibold">{sessao.eu.pessoa.nome}</span>
            <span className="block truncate text-xs text-pedra-600">
              {sessao.equipe.cargo.nome}
            </span>
          </span>
        </a>
      </div>
    </aside>
  );
}

function BarraInferior({ rota, aoNovo }: { rota: Rota; aoNovo: () => void }) {
  const { pode } = useSessao();
  const atual = itemAtual(itensVisiveis(pode), rota);
  return (
    <nav
      aria-label="Principal"
      className="fixed inset-x-0 bottom-0 z-30 flex items-end justify-around border-t border-pedra-200 bg-superficie px-2 pt-1 pb-[max(0.25rem,env(safe-area-inset-bottom))] sm:hidden"
    >
      {barraInferior(pode).map((entrada, i) =>
        entrada.tipo === "novo" ? (
          <button
            key="novo"
            type="button"
            aria-label="Novo registro"
            onClick={aoNovo}
            className="-mt-5 grid size-14 place-items-center rounded-cartao bg-pedra-900 text-superficie shadow-elevada"
          >
            <Icone nome="mais" tamanho={26} />
          </button>
        ) : entrada.item ? (
          <a
            key={entrada.item.id}
            href={caminhoDe(entrada.item.destino)}
            aria-current={atual?.id === entrada.item.id ? "page" : undefined}
            className={`flex min-h-12 min-w-14 flex-col items-center justify-center gap-0.5 rounded-controle text-[0.6875rem] font-medium ${atual?.id === entrada.item.id ? "text-sinal-500" : "text-pedra-600"}`}
            data-posicao={i}
          >
            <Icone nome={entrada.item.icone} tamanho={22} />
            {entrada.item.rotulo === "Mapa de vínculos" ? "Mapa" : entrada.item.rotulo}
          </a>
        ) : null,
      )}
    </nav>
  );
}

/**
 * A moldura do app: menu lateral fixo a partir de 640 px; abaixo disso, barra de cima enxuta e
 * barra de baixo ao alcance do polegar (AGENTS.md §2.17). A navegação deriva das permissões.
 */
export function Shell({
  rota,
  navegar,
  children,
}: {
  rota: Rota;
  navegar: (rota: Rota) => void;
  children: ReactNode;
}) {
  const sessao = useSessao();
  const itens = itensVisiveis(sessao.pode);
  const [escolhendo, setEscolhendo] = useState(false);
  const noRegistro = rota.nome === "novoRegistro" || rota.nome === "registro";

  return (
    <div className="flex min-h-dvh">
      <MenuLateral rota={rota} itens={itens} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-pedra-200 bg-superficie/95 px-4 py-2 backdrop-blur sm:px-6">
          <a href="#/" className="sm:hidden" aria-label="Início">
            <Marca className="text-lg" />
          </a>
          <BuscaGlobal
            className="hidden max-w-md flex-1 sm:block"
            aoBuscar={(termo) => navegar({ nome: "busca", termo })}
          />
          <div className="ml-auto flex items-center gap-2">
            {sessao.eu.equipes.length > 1 ? (
              <label className="hidden text-sm sm:block">
                <span className="sr-only">Equipe</span>
                <select
                  value={sessao.equipe.id}
                  onChange={(e) => sessao.trocarEquipe(Number(e.target.value))}
                  className="min-h-11 rounded-controle border border-pedra-300 bg-superficie px-3 text-sm"
                >
                  {sessao.eu.equipes.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.nome}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <SinoDeNotificacoes />
            <a href="#/perfil" aria-label="Perfil" className="sm:hidden">
              <Avatar nome={sessao.eu.pessoa.nome} tamanho={44} escuro />
            </a>
          </div>
        </header>
        <main
          className={`mx-auto w-full max-w-6xl flex-1 px-4 py-5 sm:px-6 sm:py-8 ${noRegistro ? "pb-28" : "pb-24"} sm:pb-8`}
        >
          <BuscaGlobal
            className="mb-4 sm:hidden"
            aoBuscar={(termo) => navegar({ nome: "busca", termo })}
          />
          {children}
        </main>
      </div>
      {noRegistro ? null : <BarraInferior rota={rota} aoNovo={() => setEscolhendo(true)} />}
      {escolhendo ? (
        <SeletorDeFormulario
          aoFechar={() => setEscolhendo(false)}
          aoEscolher={(formularioId) => {
            setEscolhendo(false);
            navegar({ nome: "novoRegistro", formularioId });
          }}
        />
      ) : null}
    </div>
  );
}
