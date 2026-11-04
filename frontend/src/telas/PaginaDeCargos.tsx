import { useCallback, useEffect, useMemo, useState } from "react";
import type { Cargo, Permissao } from "../api/cliente";
import { useApi } from "../api/contexto";
import { useSessao } from "../auth/sessao";
import { mensagemDoErro } from "../lib/erros";
import { Aviso, Botao, CampoDeTexto, Esqueleto, Gaveta, Interruptor } from "../ui";

/** Agrupa o catálogo do servidor pelo `grupo` de cada permissão, mantendo a ordem em que vieram. */
export function agruparPermissoes(permissoes: Permissao[]): [string, Permissao[]][] {
  const grupos = new Map<string, Permissao[]>();
  for (const p of permissoes) grupos.set(p.grupo, [...(grupos.get(p.grupo) ?? []), p]);
  return [...grupos.entries()];
}

export function PaginaDeCargos() {
  const api = useApi();
  const { recarregar } = useSessao();
  const [cargos, setCargos] = useState<Cargo[] | null>(null);
  const [catalogo, setCatalogo] = useState<Permissao[]>([]);
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState(false);
  const [novo, setNovo] = useState(false);

  const carregar = useCallback(
    async (manter?: number) => {
      try {
        const [lista, cat] = await Promise.all([api.listarCargos(), api.catalogoDePermissoes()]);
        setCargos(lista);
        setCatalogo(cat.permissoes);
        const id = manter ?? lista[0]?.id ?? null;
        setSelecionado(id);
        setMarcadas(new Set(lista.find((c) => c.id === id)?.permissoes ?? []));
      } catch (e) {
        setErro(mensagemDoErro(e));
        setCargos([]);
      }
    },
    [api],
  );

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- carga inicial da tela
    void carregar();
  }, [carregar]);

  const atual = cargos?.find((c) => c.id === selecionado) ?? null;
  const grupos = useMemo(() => agruparPermissoes(catalogo), [catalogo]);
  const alterado =
    atual !== null &&
    (atual.permissoes.length !== marcadas.size || atual.permissoes.some((p) => !marcadas.has(p)));

  function escolher(c: Cargo) {
    setSelecionado(c.id);
    setMarcadas(new Set(c.permissoes));
    setErro(null);
    setSalvo(false);
  }

  async function salvar() {
    if (!atual) return;
    setErro(null);
    try {
      await api.atualizarCargo(atual.id, {
        nome: atual.nome,
        descricao: atual.descricao,
        permissoes: [...marcadas],
      });
      setSalvo(true);
      await carregar(atual.id);
      await recarregar(); // o próprio cargo da pessoa pode ter mudado
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  async function excluir() {
    if (!atual) return;
    setErro(null);
    try {
      await api.excluirCargo(atual.id);
      await carregar();
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold">Cargos e permissões</h1>
          <p className="mt-1 max-w-xl text-sm text-pedra-600">
            Cada cargo é um conjunto de permissões: quem tem o cargo só vê e faz o que está marcado.
          </p>
        </div>
        <Botao variante="escuro" onClick={() => setNovo(true)}>
          Novo cargo
        </Botao>
      </header>
      {erro ? <Aviso tom="erro">{erro}</Aviso> : null}

      {cargos === null ? (
        <div role="status" aria-label="Carregando" className="flex flex-col gap-2">
          <Esqueleto className="h-20 rounded-cartao" />
          <Esqueleto className="h-64 rounded-cartao" />
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
          <ul className="flex flex-col gap-2" aria-label="Cargos">
            {cargos.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  aria-pressed={c.id === selecionado}
                  onClick={() => escolher(c)}
                  className={`w-full rounded-cartao border bg-superficie p-3 text-left ${c.id === selecionado ? "border-sinal-500 ring-1 ring-sinal-500" : "border-pedra-200"}`}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-bold">{c.nome}</span>
                    <span className="text-xs text-pedra-500">
                      {c.pessoas} {c.pessoas === 1 ? "pessoa" : "pessoas"}
                    </span>
                  </span>
                  <span className="mt-1 block text-xs text-pedra-600">{c.descricao}</span>
                </button>
              </li>
            ))}
            <li className="px-1 text-xs text-pedra-600">
              Sempre existe ao menos um administrador. O servidor confere a permissão em toda
              requisição: esconder um botão não é proteção.
            </li>
          </ul>

          {atual ? (
            <section
              aria-label={`Permissões de ${atual.nome}`}
              className="rounded-cartao border border-pedra-200 bg-superficie p-4 shadow-cartao"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-xl font-bold">{atual.nome}</h2>
                  <p className="font-mono text-xs text-pedra-600">
                    {marcadas.size} de {catalogo.length} permissões
                  </p>
                </div>
                <div className="flex gap-2">
                  <Botao
                    variante="perigo"
                    tamanho="pequeno"
                    disabled={atual.pessoas > 0}
                    onClick={() => void excluir()}
                  >
                    Excluir cargo
                  </Botao>
                  <Botao variante="primario" disabled={!alterado} onClick={() => void salvar()}>
                    Salvar
                  </Botao>
                </div>
              </div>
              {salvo && !alterado ? (
                <div className="mt-3">
                  <Aviso tom="sucesso">Cargo salvo.</Aviso>
                </div>
              ) : null}
              {atual.pessoas > 0 ? (
                <p className="mt-2 text-xs text-pedra-600">
                  Cargo em uso não pode ser excluído: mude o cargo das pessoas antes.
                </p>
              ) : null}
              {grupos.map(([grupo, lista]) => (
                <div key={grupo} className="mt-4">
                  <h3 className="mb-1 text-[0.6875rem] font-semibold tracking-wider text-pedra-500 uppercase">
                    {grupo}
                  </h3>
                  {lista.map((p) => (
                    <Interruptor
                      key={p.id}
                      rotulo={p.rotulo}
                      descricao={p.descricao}
                      ligado={marcadas.has(p.id)}
                      aoMudar={(ligar) => {
                        const proximo = new Set(marcadas);
                        if (ligar) proximo.add(p.id);
                        else proximo.delete(p.id);
                        setMarcadas(proximo);
                        setSalvo(false);
                      }}
                    />
                  ))}
                </div>
              ))}
            </section>
          ) : null}
        </div>
      )}

      {novo ? (
        <GavetaDeNovoCargo
          aoFechar={() => setNovo(false)}
          aoCriar={async (id) => {
            setNovo(false);
            await carregar(id);
          }}
        />
      ) : null}
    </div>
  );
}

function GavetaDeNovoCargo({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void;
  aoCriar: (id: number) => Promise<void>;
}) {
  const api = useApi();
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  async function criar() {
    try {
      // Nasce sem permissões: a pessoa liga só o que o cargo deve poder fazer.
      const cargo = await api.criarCargo({
        nome: nome.trim(),
        descricao: descricao.trim(),
        permissoes: [],
      });
      await aoCriar(cargo.id);
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  return (
    <Gaveta
      titulo="Novo cargo"
      subtitulo="Comece sem permissões e ligue o que for preciso."
      aoFechar={aoFechar}
    >
      <form
        className="flex flex-col gap-4 p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void criar();
        }}
      >
        <CampoDeTexto
          rotulo="Nome"
          required
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
        <CampoDeTexto
          rotulo="Descrição"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
        />
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <Botao type="submit" variante="primario" disabled={!nome.trim()}>
          Criar cargo
        </Botao>
      </form>
    </Gaveta>
  );
}
