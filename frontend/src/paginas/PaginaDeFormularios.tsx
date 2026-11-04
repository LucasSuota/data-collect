import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useState, type FormEvent } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type ResumoDeFormulario } from "../api/cliente";
import type { Rota } from "../rotas";
import { ComPermissao } from "../shell/permissoes";
import {
  Aviso,
  Botao,
  CampoDeBusca,
  CampoDeTexto,
  Cartao,
  EstadoVazio,
  Icone,
  Selecao,
} from "../ui";
import { ArvoreDePastas } from "./ArvoreDePastas";
import { EsqueletoDaLista } from "./esqueletos";
import { Falha, mensagemDe, mensagemDetalhada, useCarga } from "./Estado";
import {
  ORDENS,
  listarDaTela,
  rotuloDoCaminho,
  type EscopoDaBusca,
  type OrdemDaLista,
} from "./filtros";
import { LinhaDeFormulario } from "./LinhaDeFormulario";
import {
  INSTRUCOES_DE_ARRASTE,
  anunciosDeArraste,
  caminhoAte,
  destinosDeMovimento,
  ID_DA_RAIZ,
  idDeArraste,
  idDeDestino,
  resolverMovimento,
  type Pasta,
} from "./pastas";

type Dados = [ResumoDeFormulario[], Pasta[]];

interface Props {
  navegar: (rota: Rota) => void;
  /** A pasta aberta; ausente ou `null` é a raiz. */
  pastaId?: number | null;
}

/** A tela inicial: pastas e formulários, para preencher, consultar, editar, mover ou excluir. */
export function PaginaDeFormularios({ navegar, pastaId = null }: Props) {
  const cliente = useApi();
  const [versao, setVersao] = useState(0);
  const carga = useCarga(
    () => Promise.all([cliente.listarFormularios(), cliente.listarPastas()]),
    [cliente, versao],
  );
  // Ao recarregar depois de mover, duplicar ou excluir, a tela continua mostrando os dados
  // anteriores em vez de voltar ao esqueleto (a árvore e os avisos não podem sumir).
  const [ultimos, setUltimos] = useState<Dados>();
  if (carga.situacao === "pronto" && carga.dados !== ultimos) setUltimos(carga.dados);
  const [aviso, setAviso] = useState<string | null>(null);
  const [copiado, setCopiado] = useState<{ id: number; nome: string } | null>(null);
  const [arrastando, setArrastando] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [escopo, setEscopo] = useState<EscopoDaBusca>("tudo");
  const [ordem, setOrdem] = useState<OrdemDaLista>("nome-asc");
  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const recarregar = () => setVersao((v) => v + 1);

  async function aoSoltar(evento: DragEndEvent) {
    setArrastando(null);
    const movimento = resolverMovimento(
      String(evento.active.id),
      evento.over?.id?.toString() ?? null,
    );
    if (movimento === null || !ultimos) return;
    const formulario = ultimos[0].find((f) => f.id === movimento.formularioId);
    // Soltar no lugar onde já está não é movimento.
    if (!formulario || (formulario.pasta_id ?? null) === movimento.pastaId) return;
    try {
      await cliente.moverFormulario(movimento.formularioId, movimento.pastaId);
      setAviso(null);
      recarregar();
    } catch (erro) {
      setAviso(mensagemDetalhada(erro));
    }
  }

  if (carga.situacao === "carregando" && !ultimos) {
    return (
      <Moldura>
        <EsqueletoDaLista />
      </Moldura>
    );
  }
  if (carga.situacao === "erro" && !ultimos) {
    return (
      <Moldura>
        <Falha mensagem={carga.mensagem} />
      </Moldura>
    );
  }

  if (!ultimos) return null; // inalcançável: sem dados, um dos retornos acima já saiu
  const [formularios, pastas] = ultimos;
  const atual = pastaId === null ? null : (pastas.find((p) => p.id === pastaId) ?? null);
  if (pastaId !== null && atual === null) {
    return (
      <Moldura>
        <Aviso tom="erro">
          Pasta não encontrada.{" "}
          <a href="#/formularios" className="underline decoration-sinal-500 underline-offset-2">
            Voltar aos formulários
          </a>
        </Aviso>
      </Moldura>
    );
  }

  const contagem = new Map<number | null, number>();
  for (const f of formularios) {
    const pasta = f.pasta_id ?? null;
    contagem.set(pasta, (contagem.get(pasta) ?? 0) + 1);
  }
  const buscando = busca.trim() !== "";
  const { pastas: subpastas, formularios: daPasta } = listarDaTela({
    formularios,
    pastas,
    atualId: atual?.id ?? null,
    termo: busca,
    escopo,
    ordem,
  });
  // Abrir uma pasta é sair da busca: o termo digitado não deve filtrar o conteúdo da pasta nova.
  const abrirPasta = (id: number | null) => {
    setBusca("");
    navegar(id === null ? { nome: "formularios" } : { nome: "pasta", pastaId: id });
  };
  const todosOsDestinos = destinosDeMovimento(pastas);
  const arrastado = arrastando
    ? formularios.find((f) => idDeArraste(f.id) === arrastando)
    : undefined;

  return (
    <DndContext
      sensors={sensores}
      accessibility={{
        announcements: anunciosDeArraste({
          formulario: (id) => formularios.find((f) => idDeArraste(f.id) === id)?.nome ?? null,
          destino: (id) =>
            id === ID_DA_RAIZ
              ? "Todos os formulários"
              : (pastas.find((p) => idDeDestino(p.id) === id)?.nome ?? null),
        }),
        screenReaderInstructions: { draggable: INSTRUCOES_DE_ARRASTE },
      }}
      onDragStart={(evento) => setArrastando(String(evento.active.id))}
      onDragEnd={(evento) => void aoSoltar(evento)}
      onDragCancel={() => setArrastando(null)}
    >
      <Moldura
        lateral={
          <ArvoreDePastas
            pastas={pastas}
            atual={atual?.id ?? null}
            contagem={contagem}
            abrir={abrirPasta}
          />
        }
      >
        <Cabecalho
          atual={atual}
          pastas={pastas}
          navegar={navegar}
          aoAlterar={recarregar}
          aoFalhar={setAviso}
        />

        {aviso ? <Falha mensagem={aviso} /> : null}
        {carga.situacao === "erro" ? <Falha mensagem={carga.mensagem} /> : null}
        {copiado ? (
          <Aviso
            tom="sucesso"
            acoes={
              <Botao
                tamanho="pequeno"
                onClick={() => navegar({ nome: "editarFormulario", formularioId: copiado.id })}
              >
                Editar a cópia
              </Botao>
            }
          >
            «{copiado.nome}» foi criado. Os registros não foram copiados, só a definição atual.
          </Aviso>
        ) : null}

        {formularios.length > 0 || pastas.length > 0 ? (
          <BarraDeFiltros
            busca={busca}
            aoBuscar={setBusca}
            ordem={ordem}
            aoOrdenar={setOrdem}
            escopo={atual ? escopo : null}
            aoEscolherEscopo={setEscopo}
            nomeDaPasta={atual?.nome}
            resultado={buscando ? { formularios: daPasta.length, pastas: subpastas.length } : null}
          />
        ) : null}

        {subpastas.length > 0 ? (
          <ul
            aria-label={buscando ? "Pastas encontradas" : "Pastas desta pasta"}
            className="grid grid-cols-2 gap-3 md:grid-cols-3"
          >
            {subpastas.map((subpasta) => (
              <CartaoDePasta
                key={subpasta.id}
                pasta={subpasta}
                formularios={contagem.get(subpasta.id) ?? 0}
                subpastas={pastas.filter((p) => p.pasta_pai_id === subpasta.id).length}
                caminho={
                  buscando && subpasta.pasta_pai_id !== null
                    ? rotuloDoCaminho(pastas, subpasta.pasta_pai_id)
                    : undefined
                }
                abrir={() => abrirPasta(subpasta.id)}
              />
            ))}
          </ul>
        ) : null}

        {buscando && daPasta.length === 0 && subpastas.length === 0 ? (
          <EstadoVazio
            icone="busca"
            titulo="Nada encontrado"
            acao={<Botao onClick={() => setBusca("")}>Limpar a busca</Botao>}
          >
            Nenhum formulário ou pasta combina com «{busca.trim()}»
            {atual && escopo === "pasta" ? " nesta pasta" : ""}.
          </EstadoVazio>
        ) : null}

        {!buscando && daPasta.length === 0 && subpastas.length === 0 ? (
          <EstadoVazio
            icone={atual ? "pasta" : "registros"}
            titulo={atual ? "Esta pasta está vazia" : "Nenhum formulário ainda"}
            acao={
              <Botao
                variante="primario"
                onClick={() =>
                  navegar(
                    atual
                      ? { nome: "novoFormulario", pastaId: atual.id }
                      : { nome: "novoFormulario" },
                  )
                }
              >
                <Icone nome="mais" />
                {atual ? "Criar um formulário aqui" : "Criar o primeiro no construtor"}
              </Botao>
            }
          >
            {atual
              ? "Crie um formulário aqui ou arraste um da lista para dentro desta pasta."
              : "Um formulário é montado no construtor e depois preenchido quantas vezes for preciso."}
          </EstadoVazio>
        ) : null}

        {daPasta.length > 0 ? (
          <Cartao>
            <ul className="divide-y divide-pedra-200">
              {daPasta.map((formulario) => (
                <LinhaDeFormulario
                  key={formulario.id}
                  formulario={formulario}
                  destinos={todosOsDestinos.filter((d) => d.id !== (formulario.pasta_id ?? null))}
                  caminho={
                    buscando ? rotuloDoCaminho(pastas, formulario.pasta_id ?? null) : undefined
                  }
                  navegar={navegar}
                  aoAlterar={recarregar}
                  aoCopiado={(copia) => {
                    setCopiado(copia);
                    setAviso(null);
                  }}
                  aoFalhar={setAviso}
                />
              ))}
            </ul>
          </Cartao>
        ) : null}
      </Moldura>
      <DragOverlay dropAnimation={null}>
        {arrastado ? (
          <div className="flex items-center gap-2 rounded-cartao border border-sinal-500 bg-superficie px-3 py-2 text-sm font-medium shadow-elevada">
            <Icone nome="registros" className="text-pedra-500" />
            {arrastado.nome}
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

/** O esqueleto da tela: título e "Novo formulário" sempre no mesmo lugar, com ou sem a árvore. */
function Moldura({ lateral, children }: { lateral?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-8 md:grid-cols-[15rem_1fr]">
      <aside className="md:sticky md:top-6 md:self-start">{lateral}</aside>
      <section className="flex min-w-0 flex-col gap-5">
        {lateral === undefined ? (
          <h1 className="text-2xl font-semibold tracking-tight">Formulários</h1>
        ) : null}
        {children}
      </section>
    </div>
  );
}

/** Busca por nome (formulários e pastas), onde buscar e a ordem da lista. */
function BarraDeFiltros({
  busca,
  aoBuscar,
  ordem,
  aoOrdenar,
  escopo,
  aoEscolherEscopo,
  nomeDaPasta,
  resultado,
}: {
  busca: string;
  aoBuscar: (valor: string) => void;
  ordem: OrdemDaLista;
  aoOrdenar: (ordem: OrdemDaLista) => void;
  /** `null` na raiz, onde buscar "só aqui" não faz sentido. */
  escopo: EscopoDaBusca | null;
  aoEscolherEscopo: (escopo: EscopoDaBusca) => void;
  nomeDaPasta?: string;
  /** `null` sem busca. */
  resultado: { formularios: number; pastas: number } | null;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div role="search" className="flex flex-wrap items-center gap-2">
        <CampoDeBusca
          rotulo="Buscar formulários e pastas"
          placeholder="Buscar formulários e pastas"
          className="min-w-56 flex-1"
          valor={busca}
          aoMudar={aoBuscar}
        />
        {escopo !== null ? (
          <Selecao
            rotulo="Onde buscar"
            ocultarRotulo
            tamanho="normal"
            value={escopo}
            onChange={(e) => aoEscolherEscopo(e.target.value as EscopoDaBusca)}
          >
            <option value="tudo">Em todas as pastas</option>
            <option value="pasta">Só em {nomeDaPasta}</option>
          </Selecao>
        ) : null}
        <Selecao
          rotulo="Ordenar por"
          ocultarRotulo
          tamanho="normal"
          value={ordem}
          onChange={(e) => aoOrdenar(e.target.value as OrdemDaLista)}
        >
          {ORDENS.map((o) => (
            <option key={o.valor} value={o.valor}>
              Ordenar: {o.rotulo}
            </option>
          ))}
        </Selecao>
      </div>
      {resultado ? (
        <p role="status" className="text-sm text-pedra-600">
          {textoDoResultado(resultado)}
        </p>
      ) : null}
    </div>
  );
}

function textoDoResultado({ formularios, pastas }: { formularios: number; pastas: number }) {
  const plural = (n: number, singular: string, mais: string) => `${n} ${n === 1 ? singular : mais}`;
  return `Encontrado${formularios + pastas === 1 ? "" : "s"}: ${plural(formularios, "formulário", "formulários")} e ${plural(pastas, "pasta", "pastas")}.`;
}

function CartaoDePasta({
  pasta,
  formularios,
  subpastas,
  caminho,
  abrir,
}: {
  pasta: Pasta;
  formularios: number;
  subpastas: number;
  /** Onde a pasta está, quando a lista mistura níveis (resultado de busca). */
  caminho?: string;
  abrir: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: idDeDestino(pasta.id) });
  const resumo = [
    formularios > 0 ? `${formularios} formulário${formularios > 1 ? "s" : ""}` : null,
    subpastas > 0 ? `${subpastas} subpasta${subpastas > 1 ? "s" : ""}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <li ref={setNodeRef}>
      <button
        type="button"
        onClick={abrir}
        className={`flex w-full items-center gap-3 rounded-cartao border bg-superficie p-3.5 text-left shadow-cartao transition-colors duration-(--duracao-rapida) hover:border-pedra-400 ${isOver ? "border-sinal-500 bg-sinal-100" : "border-pedra-200"}`}
      >
        <span className="grid size-9 shrink-0 place-items-center rounded-controle bg-pedra-100 text-pedra-600">
          <Icone nome="pasta" />
        </span>
        <span className="min-w-0">
          <span className="block truncate font-medium">{pasta.nome}</span>
          {caminho ? (
            <span className="block truncate text-sm text-pedra-500">em {caminho}</span>
          ) : null}
          <span className="block text-sm text-pedra-500">{resumo || "Vazia"}</span>
        </span>
      </button>
    </li>
  );
}

/** Trilha, título e ações da pasta aberta (criar subpasta, renomear, mover, excluir). */
function Cabecalho({
  atual,
  pastas,
  navegar,
  aoAlterar,
  aoFalhar,
}: {
  atual: Pasta | null;
  pastas: Pasta[];
  navegar: (rota: Rota) => void;
  aoAlterar: () => void;
  aoFalhar: (mensagem: string | null) => void;
}) {
  const cliente = useApi();
  const [criando, setCriando] = useState(false);
  const [renomeando, setRenomeando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [nome, setNome] = useState("");
  const [erros, setErros] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);

  const trilha = caminhoAte(pastas, atual?.id ?? null);

  async function enviar(evento: FormEvent, acao: () => Promise<unknown>, aoConcluir: () => void) {
    evento.preventDefault();
    setSalvando(true);
    try {
      await acao();
      aoConcluir();
      aoFalhar(null);
      aoAlterar();
    } catch (erro) {
      // 422: nome repetido no mesmo local vem no campo `nome`.
      const doNome = erro instanceof ErroDaApi ? erro.mensagensPorCampo()["nome"] : undefined;
      setErros(doNome ?? [mensagemDe(erro)]);
    } finally {
      setSalvando(false);
    }
  }

  async function mover(valor: string) {
    if (!atual || valor === "") return;
    try {
      await cliente.atualizarPasta(atual.id, atual.nome, valor === "raiz" ? null : Number(valor));
      aoFalhar(null);
      aoAlterar();
    } catch (erro) {
      aoFalhar(mensagemDetalhada(erro));
    }
  }

  async function excluir() {
    if (!atual) return;
    try {
      await cliente.excluirPasta(atual.id);
      navegar(
        atual.pasta_pai_id === null
          ? { nome: "formularios" }
          : { nome: "pasta", pastaId: atual.pasta_pai_id },
      );
    } catch (erro) {
      // 409: o servidor explica que a pasta ainda tem subpastas ou formulários.
      aoFalhar(mensagemDe(erro));
    } finally {
      setConfirmando(false);
    }
  }

  const destinos = atual
    ? destinosDeMovimento(pastas, atual.id).filter((d) => d.id !== atual.pasta_pai_id)
    : [];

  return (
    <header className="flex flex-col gap-3">
      <nav aria-label="Caminho da pasta" className="flex flex-wrap items-center gap-1 text-sm">
        <a
          href="#/formularios"
          className="rounded-controle text-pedra-600 hover:text-pedra-900"
          onClick={(e) => {
            e.preventDefault();
            navegar({ nome: "formularios" });
          }}
        >
          Formulários
        </a>
        {trilha.map((pasta, indice) => (
          <span key={pasta.id} className="flex items-center gap-1">
            <Icone nome="seta" tamanho={12} className="text-pedra-400" />
            {indice === trilha.length - 1 ? (
              <span aria-current="page" className="font-medium text-pedra-900">
                {pasta.nome}
              </span>
            ) : (
              <a
                href={`#/pastas/${pasta.id}`}
                className="rounded-controle text-pedra-600 hover:text-pedra-900"
                onClick={(e) => {
                  e.preventDefault();
                  navegar({ nome: "pasta", pastaId: pasta.id });
                }}
              >
                {pasta.nome}
              </a>
            )}
          </span>
        ))}
      </nav>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{atual?.nome ?? "Formulários"}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <ComPermissao permissao="formularios:organizar">
            <Botao
              onClick={() => {
                setCriando(true);
                setRenomeando(false);
                setNome("");
                setErros([]);
              }}
            >
              <Icone nome="pasta" />
              Nova pasta
            </Botao>
          </ComPermissao>
          <ComPermissao permissao="formularios:publicar" bloqueado="Novo formulário">
            <Botao
              variante="primario"
              onClick={() =>
                navegar(
                  atual
                    ? { nome: "novoFormulario", pastaId: atual.id }
                    : { nome: "novoFormulario" },
                )
              }
            >
              <Icone nome="mais" />
              Novo formulário
            </Botao>
          </ComPermissao>
        </div>
      </div>

      {atual ? (
        <div className="flex flex-wrap items-center gap-2">
          <Botao
            variante="fantasma"
            tamanho="pequeno"
            aria-label="Renomear a pasta"
            onClick={() => {
              setRenomeando(true);
              setCriando(false);
              setNome(atual.nome);
              setErros([]);
            }}
          >
            <Icone nome="editar" />
            Renomear
          </Botao>
          <Selecao
            rotulo="Mover a pasta para"
            ocultarRotulo
            value=""
            onChange={(e) => void mover(e.target.value)}
          >
            <option value="">Mover para…</option>
            {atual.pasta_pai_id !== null ? <option value="raiz">Raiz (sem pasta)</option> : null}
            {destinos.map((d) => (
              <option key={d.id} value={d.id}>
                {d.rotulo}
              </option>
            ))}
          </Selecao>
          {confirmando ? (
            <Botao variante="perigoSolido" tamanho="pequeno" onClick={() => void excluir()}>
              Confirmar exclusão da pasta
            </Botao>
          ) : (
            <Botao
              variante="perigo"
              tamanho="pequeno"
              aria-label="Excluir a pasta"
              onClick={() => setConfirmando(true)}
            >
              <Icone nome="lixeira" />
              Excluir
            </Botao>
          )}
        </div>
      ) : null}

      {criando ? (
        <form
          className="flex flex-col gap-3 rounded-cartao bg-pedra-100 p-4"
          onSubmit={(e) =>
            void enviar(
              e,
              () => cliente.criarPasta(nome.trim(), atual?.id ?? null),
              () => setCriando(false),
            )
          }
        >
          <CampoDeTexto
            autoFocus
            rotulo="Nome da pasta"
            value={nome}
            erros={erros}
            onChange={(e) => {
              setNome(e.target.value);
              setErros([]);
            }}
          />
          <div className="flex gap-2">
            <Botao type="submit" variante="primario" carregando={salvando}>
              Criar pasta
            </Botao>
            <Botao onClick={() => setCriando(false)}>Cancelar</Botao>
          </div>
        </form>
      ) : null}

      {renomeando && atual ? (
        <form
          className="flex flex-col gap-3 rounded-cartao bg-pedra-100 p-4"
          onSubmit={(e) =>
            void enviar(
              e,
              () => cliente.atualizarPasta(atual.id, nome.trim(), atual.pasta_pai_id),
              () => setRenomeando(false),
            )
          }
        >
          <CampoDeTexto
            autoFocus
            rotulo="Novo nome"
            value={nome}
            erros={erros}
            onChange={(e) => {
              setNome(e.target.value);
              setErros([]);
            }}
          />
          <div className="flex gap-2">
            <Botao type="submit" variante="primario" carregando={salvando}>
              Salvar nome
            </Botao>
            <Botao onClick={() => setRenomeando(false)}>Cancelar</Botao>
          </div>
        </form>
      ) : null}
    </header>
  );
}
