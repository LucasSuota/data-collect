import { useCallback, useEffect, useState } from "react";
import type { Cargo, Convite, Membro } from "../api/cliente";
import { useApi } from "../api/contexto";
import { useSessao } from "../auth/sessao";
import { mensagemDoErro } from "../lib/erros";
import { Avatar } from "../shell/Avatar";
import { ComPermissao } from "../shell/permissoes";
import {
  Aviso,
  Botao,
  CampoDeTexto,
  Esqueleto,
  EstadoVazio,
  Gaveta,
  Icone,
  Selecao,
  SeloDeCargo,
} from "../ui";

type Aba = "ativos" | "convites" | "inativos";

export function linkDoConvite(token: string, origem = window.location.origin): string {
  return `${origem}/convite/${token}`;
}

export function PaginaDaEquipe() {
  const api = useApi();
  const { eu, pode, equipe } = useSessao();
  const [aba, setAba] = useState<Aba>("ativos");
  const [membros, setMembros] = useState<Membro[] | null>(null);
  const [convites, setConvites] = useState<Convite[]>([]);
  const [cargos, setCargos] = useState<Cargo[]>([]);
  const [convidando, setConvidando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const [m, c] = await Promise.all([
        api.listarMembros(),
        pode("equipe:convidar") ? api.listarConvites() : Promise.resolve([]),
      ]);
      setMembros(m);
      setConvites(c);
      setCargos(await api.listarCargos());
    } catch (e) {
      setErro(mensagemDoErro(e));
      setMembros((atual) => atual ?? []);
    }
  }, [api, pode]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial da tela
    void carregar();
  }, [carregar]);

  async function agir(acao: () => Promise<void>) {
    setErro(null);
    try {
      await acao();
      await carregar();
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  const ativos = (membros ?? []).filter((m) => m.ativo);
  const inativos = (membros ?? []).filter((m) => !m.ativo);
  const abas: [Aba, string, number][] = [
    ["ativos", "Ativos", ativos.length],
    ["convites", "Convites", convites.length],
    ["inativos", "Inativos", inativos.length],
  ];

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-center justify-between gap-3">
        <h1 className="text-3xl font-extrabold">Equipe</h1>
        <ComPermissao permissao="equipe:convidar" bloqueado="Convidar">
          <Botao variante="primario" onClick={() => setConvidando(true)}>
            <Icone nome="mais" /> Convidar
          </Botao>
        </ComPermissao>
      </header>
      <p className="-mt-3 text-sm text-pedra-600">{equipe.nome}</p>

      <div
        role="tablist"
        aria-label="Pessoas"
        className="grid grid-cols-3 gap-1 rounded-cartao bg-pedra-200/70 p-1"
      >
        {abas.map(([id, rotulo, total]) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={aba === id}
            onClick={() => setAba(id)}
            className={`min-h-11 rounded-controle text-sm font-semibold ${aba === id ? "bg-superficie shadow-cartao" : "text-pedra-600"}`}
          >
            {rotulo} · {total}
          </button>
        ))}
      </div>

      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}

      {membros === null ? (
        <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
          <Esqueleto className="h-16 rounded-cartao" />
          <Esqueleto className="h-16 rounded-cartao" />
          <Esqueleto className="h-16 rounded-cartao" />
        </div>
      ) : aba === "convites" ? (
        convites.length === 0 ? (
          <EstadoVazio icone="usuarios" titulo="Nenhum convite pendente">
            Convide alguém pelo e-mail: a pessoa recebe um link para criar a conta e entra com o
            cargo que você escolher.
          </EstadoVazio>
        ) : (
          <ul className="flex flex-col gap-2">
            {convites.map((c) => (
              <li
                key={c.id}
                className="flex items-center gap-3 rounded-cartao border border-pedra-200 bg-superficie p-3 shadow-cartao"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold">{c.email}</p>
                  <p className="mt-0.5 flex items-center gap-2 text-xs text-pedra-600">
                    <SeloDeCargo nome={c.cargo.nome} /> expira em{" "}
                    {new Date(c.expira_em).toLocaleDateString("pt-BR")}
                  </p>
                </div>
                <Botao
                  variante="perigo"
                  tamanho="pequeno"
                  onClick={() => void agir(() => api.revogarConvite(c.id))}
                >
                  Revogar
                </Botao>
              </li>
            ))}
          </ul>
        )
      ) : (
        <ul className="flex flex-col gap-2">
          {(aba === "ativos" ? ativos : inativos).map((m) => (
            <LinhaDePessoa
              key={m.usuario_id}
              membro={m}
              voce={m.usuario_id === eu.pessoa.id}
              cargos={cargos}
              agir={agir}
            />
          ))}
          {(aba === "ativos" ? ativos : inativos).length === 0 ? (
            <li>
              <EstadoVazio icone="usuarios" titulo="Ninguém por aqui" />
            </li>
          ) : null}
        </ul>
      )}

      <ComPermissao permissao="cargos:editar">
        <a
          href="#/cargos"
          className="flex min-h-12 items-center justify-between rounded-cartao border border-dashed border-pedra-400 px-4 text-sm font-semibold hover:bg-pedra-100"
        >
          <span className="inline-flex items-center gap-2">
            <Icone nome="escudo" /> Gerenciar cargos e permissões
          </span>
          <Icone nome="seta" />
        </a>
      </ComPermissao>

      {convidando ? (
        <GavetaDeConvite
          cargos={cargos}
          aoFechar={() => {
            setConvidando(false);
            void carregar();
          }}
        />
      ) : null}
    </div>
  );
}

function LinhaDePessoa({
  membro,
  voce,
  cargos,
  agir,
}: {
  membro: Membro;
  voce: boolean;
  cargos: Cargo[];
  agir: (acao: () => Promise<void>) => Promise<void>;
}) {
  const api = useApi();
  const { pode } = useSessao();
  const [aberto, setAberto] = useState(false);
  const podeTrocar = pode("equipe:atribuir_cargos") && !voce && membro.ativo;
  const podeDesativar = pode("equipe:convidar") && !voce;

  return (
    <li className="rounded-cartao border border-pedra-200 bg-superficie p-3 shadow-cartao">
      <div className="flex items-center gap-3">
        <Avatar nome={membro.nome} escuro={voce} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">
            {membro.nome}
            {voce ? <span className="font-normal text-pedra-600"> (você)</span> : null}
          </p>
          <SeloDeCargo nome={membro.cargo.nome} />
        </div>
        {podeTrocar || podeDesativar ? (
          <button
            type="button"
            aria-label={`Ações de ${membro.nome}`}
            aria-expanded={aberto}
            onClick={() => setAberto((v) => !v)}
            className="grid size-11 place-items-center rounded-controle hover:bg-pedra-100"
          >
            <Icone nome="pontos" />
          </button>
        ) : null}
      </div>
      {aberto ? (
        <div className="mt-3 flex flex-col gap-2 border-t border-pedra-200 pt-3 sm:flex-row sm:items-end">
          {podeTrocar ? (
            <div className="flex-1">
              <Selecao
                rotulo="Cargo"
                tamanho="normal"
                value={membro.cargo.id}
                onChange={(e) =>
                  void agir(() => api.trocarCargo(membro.usuario_id, Number(e.target.value)))
                }
              >
                {cargos.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </Selecao>
            </div>
          ) : null}
          {podeDesativar ? (
            membro.ativo ? (
              <Botao
                variante="perigo"
                onClick={() => void agir(() => api.desativarMembro(membro.usuario_id))}
              >
                Desativar acesso
              </Botao>
            ) : (
              <Botao onClick={() => void agir(() => api.reativarMembro(membro.usuario_id))}>
                Reativar
              </Botao>
            )
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function GavetaDeConvite({ cargos, aoFechar }: { cargos: Cargo[]; aoFechar: () => void }) {
  const api = useApi();
  const [email, setEmail] = useState("");
  const [cargoId, setCargoId] = useState<number | null>(
    cargos.find((c) => c.nome === "Técnico")?.id ?? cargos[0]?.id ?? null,
  );
  const [erro, setErro] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    if (cargoId === null) return;
    setEnviando(true);
    setErro(null);
    try {
      const criado = await api.criarConvite(email.trim(), cargoId);
      setLink(linkDoConvite(criado.token));
    } catch (e) {
      setErro(mensagemDoErro(e));
    } finally {
      setEnviando(false);
    }
  }

  async function copiar() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopiado(true);
    } catch {
      setErro("Não foi possível copiar. Selecione o link e copie à mão.");
    }
  }

  return (
    <Gaveta
      titulo="Convidar pessoa"
      subtitulo="A pessoa cria a conta pelo link e entra com este cargo."
      aoFechar={aoFechar}
    >
      <div className="flex flex-col gap-4 p-4">
        {link ? (
          <>
            <Aviso tom="sucesso">
              Convite criado. Envie este link para {email}: ele só aparece agora e vale por tempo
              limitado.
            </Aviso>
            <input
              readOnly
              value={link}
              aria-label="Link do convite"
              onFocus={(e) => e.currentTarget.select()}
              className="min-h-11 rounded-controle border border-pedra-300 bg-superficie px-3 font-mono text-xs"
            />
            <Botao variante="primario" onClick={() => void copiar()}>
              {copiado ? "Link copiado" : "Copiar link"}
            </Botao>
            <Botao onClick={aoFechar}>Concluir</Botao>
          </>
        ) : (
          <form
            className="flex flex-col gap-4"
            onSubmit={(e) => {
              e.preventDefault();
              void enviar();
            }}
          >
            <CampoDeTexto
              rotulo="E-mail"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="pessoa@empresa.com.br"
            />
            <Selecao
              rotulo="Cargo"
              tamanho="normal"
              value={cargoId ?? ""}
              onChange={(e) => setCargoId(Number(e.target.value))}
            >
              {cargos.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </Selecao>
            {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
            <Botao type="submit" variante="primario" carregando={enviando} disabled={!email.trim()}>
              Criar convite
            </Botao>
          </form>
        )}
      </div>
    </Gaveta>
  );
}
