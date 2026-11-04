import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Fragment, useEffect, useRef, useState } from "react";
import { useApi } from "../api/contexto";
import {
  ErroDaApi,
  type Esquemas,
  type FormularioDetalhe,
  type Pasta,
  type Rascunho as RascunhoDeVersao,
  type TipoDeCampo,
} from "../api/cliente";
import { ComPermissao } from "../shell/permissoes";
import type { Rascunho } from "../ia/rascunhos";
import { EsqueletoDoConstrutor } from "../paginas/esqueletos";
import { Falha, mensagemDe, useCarga } from "../paginas/Estado";
import type { Rota } from "../rotas";
import { useMovimentoReduzido } from "../lib/movimentoReduzido";
import { CLASSE_DO_CONTROLE } from "../components/FormRenderer/Campo";
import { Aviso, Botao, Icone, Selo } from "../ui";
import {
  INSTRUCOES_DO_CONSTRUTOR,
  anunciosDoConstrutor,
  chaveDoCampoNovo,
  posicaoDoDestino,
} from "./arraste";
import { PainelDePropriedades } from "./PainelDePropriedades";
import { camposDeFormulaDasReferencias, useCamposDeOrigem } from "./useCamposDeOrigem";
import {
  AREA_DA_LISTA,
  adicionarCampo,
  aplicarArraste,
  atualizarCampo,
  deDefinicao,
  deRascunho,
  mapearErros,
  moverCampo,
  paraDefinicao,
  removerCampo,
  type Arrastado,
  type CampoEmEdicao,
  type ErrosMapeados,
  type PropriedadesPorTipo,
} from "./estado";

type Catalogo = Esquemas["CatalogoSaida"];

export type ModoDoConstrutor =
  | { tipo: "novo"; pastaId?: number }
  | { tipo: "editar"; formularioId: number }
  /**
   * Edita um rascunho proposto pela IA, que ainda não existe no servidor: não publica nem valida
   * sozinho (quem valida o conjunto é a publicação em lote); devolve o resultado a quem chamou.
   */
  | {
      tipo: "rascunho";
      rascunho: Rascunho;
      /** Nomes dos outros rascunhos do conjunto, que este pode referenciar. */
      nomesDosIrmaos: string[];
      aoConcluir: (nome: string, definicao: ReturnType<typeof paraDefinicao>) => void;
      aoCancelar: () => void;
    };

interface Props {
  modo: ModoDoConstrutor;
  navegar: (rota: Rota) => void;
  /** Espera antes de validar depois de uma edição (ms). */
  atrasoDaValidacaoMs?: number;
}

interface Carregado {
  catalogo: Catalogo;
  nomesDosFormularios: string[];
  /** Os formulários que podem ser origem de uma referência (o próprio fica de fora). */
  origensPossiveis: { id: number; nome: string }[];
  formulario: FormularioDetalhe | null;
  /** O rascunho da próxima versão, se a equipe já começou um (compartilhado por todos). */
  rascunhoSalvo: RascunhoDeVersao | null;
  pastas: Pasta[];
}

let proximaChave = 0;
const gerarChave = () => `campo-${++proximaChave}`;

/** Monta a definição sem editar JSON à mão: paleta, arrastar e soltar, propriedades e publicação. */
export function Construtor({ modo, navegar, atrasoDaValidacaoMs = 500 }: Props) {
  const cliente = useApi();
  const chave =
    modo.tipo === "novo"
      ? "novo"
      : modo.tipo === "editar"
        ? `editar-${modo.formularioId}`
        : `rascunho-${modo.rascunho.chave}`;

  const carga = useCarga<Carregado>(async () => {
    const [catalogo, formularios, formulario, rascunhoSalvo, pastas] = await Promise.all([
      cliente.catalogo(),
      cliente.listarFormularios(),
      modo.tipo === "editar" ? cliente.obterFormulario(modo.formularioId) : Promise.resolve(null),
      // 404 = ainda não há rascunho; qualquer falha aqui só significa começar da versão atual.
      modo.tipo === "editar"
        ? Promise.resolve()
            .then(() => cliente.obterRascunho(modo.formularioId))
            .catch(() => null)
        : Promise.resolve(null),
      Promise.resolve()
        .then(() => cliente.listarPastas())
        .catch((): Pasta[] => []),
    ]);
    return {
      catalogo,
      origensPossiveis: formularios
        .filter((f) => f.id !== formulario?.id)
        .map((f) => ({ id: f.id, nome: f.nome })),
      nomesDosFormularios: [
        ...new Set([
          ...formularios
            .filter((f) => f.id !== formulario?.id) // o formulário não pode se referenciar
            .map((f) => f.nome),
          ...(modo.tipo === "rascunho" ? modo.nomesDosIrmaos : []),
        ]),
      ],
      formulario,
      rascunhoSalvo,
      pastas,
    };
  }, [cliente, chave]);

  if (carga.situacao === "carregando") return <EsqueletoDoConstrutor />;
  if (carga.situacao === "erro") return <Falha mensagem={carga.mensagem} />;
  return (
    <Editor
      key={chave}
      modo={modo}
      carregado={carga.dados}
      navegar={navegar}
      atrasoDaValidacaoMs={atrasoDaValidacaoMs}
    />
  );
}

function Editor({
  modo,
  carregado,
  navegar,
  atrasoDaValidacaoMs,
}: {
  modo: ModoDoConstrutor;
  carregado: Carregado;
  navegar: Props["navegar"];
  atrasoDaValidacaoMs: number;
}) {
  const cliente = useApi();
  const { catalogo, formulario } = carregado;
  const editando = formulario !== null;
  const rascunho = modo.tipo === "rascunho" ? modo : null;

  const aceitas: PropriedadesPorTipo = Object.fromEntries(
    catalogo.tipos.map((tipo) => [tipo.id, tipo.propriedades]),
  );
  const rotulosDosTipos = Object.fromEntries(catalogo.tipos.map((tipo) => [tipo.id, tipo.rotulo]));

  const [nome, setNome] = useState(formulario?.nome ?? rascunho?.rascunho.nome ?? "");
  const [campos, setCampos] = useState<CampoEmEdicao[]>(() => {
    // O rascunho da equipe, se existir, vale mais que a versão publicada.
    if (formulario && carregado.rascunhoSalvo)
      return deRascunho(carregado.rascunhoSalvo.definicao, gerarChave);
    if (formulario) return deDefinicao(formulario.versao_atual.definicao, gerarChave);
    return rascunho ? deRascunho(rascunho.rascunho.definicao, gerarChave) : [];
  });
  const [selecionada, setSelecionada] = useState<string | null>(null);
  // O que está no ar (para o overlay e o indicador) e a chave do campo que acabou de entrar
  // (para a animação de entrada).
  const [arrastado, setArrastado] = useState<Arrastado | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [recemAdicionada, setRecemAdicionada] = useState<string | null>(null);
  const movimentoReduzido = useMovimentoReduzido();
  // Os erros que a IA deixou no rascunho já aparecem nos campos certos (mesma regra do publicar).
  const [erros, setErros] = useState<ErrosMapeados>(() =>
    mapearErros(
      (rascunho?.rascunho.erros ?? []).filter((e) => e.campo !== "nome"),
      campos.map(({ chave, id }) => ({ chave, id })),
    ),
  );
  const [erroDoNome, setErroDoNome] = useState<string[]>(() =>
    (rascunho?.rascunho.erros ?? []).filter((e) => e.campo === "nome").map((e) => e.mensagem),
  );
  const [falha, setFalha] = useState<string | null>(null);
  const [publicando, setPublicando] = useState(false);
  const [resultadoDaValidacao, setResultadoDaValidacao] = useState<string | null>(null);
  const [validando, setValidando] = useState(false);
  // Rascunho compartilhado da próxima versão (AGENTS.md §2.2): salva sozinho, com `revisao`.
  const revisaoDoRascunho = useRef<number | null>(carregado.rascunhoSalvo?.revisao ?? null);
  const [statusDoRascunho, setStatusDoRascunho] = useState<
    "parado" | "salvando" | "salvo" | "falhou" | "conflito"
  >(carregado.rascunhoSalvo ? "salvo" : "parado");
  const [temRascunho, setTemRascunho] = useState(carregado.rascunhoSalvo !== null);
  const primeiraRenderizacao = useRef(true);
  // Os campos exatos para os quais o publicar falhou. Enquanto não houver edição, a validação
  // não roda: ela apagaria os erros que só o publicar conhece (contrato entre versões).
  const camposComErroDePublicacao = useRef<CampoEmEdicao[] | null>(null);

  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Valida no servidor (o front não conhece a gramática), com debounce. O instantâneo guarda a
  // ordem enviada: o índice de `campos[3].id` vale para ela, não para a ordem de depois.
  useEffect(() => {
    // Rascunho: o conjunto só pode ser validado junto, na publicação em lote.
    if (campos.length === 0 || rascunho) return;
    const instantaneo = campos.map(({ chave, id }) => ({ chave, id }));
    let obsoleto = false;
    const temporizador = setTimeout(() => {
      if (camposComErroDePublicacao.current === campos) return;
      cliente.validarDefinicao(paraDefinicao(campos, aceitas)).then(
        (resultado) => {
          if (!obsoleto && camposComErroDePublicacao.current !== campos) {
            setErros(mapearErros(resultado.erros, instantaneo));
          }
        },
        () => undefined, // sem conexão: o publicar mostra o motivo
      );
    }, atrasoDaValidacaoMs);
    return () => {
      obsoleto = true;
      clearTimeout(temporizador);
    };
    // `aceitas` deriva do catálogo, que não muda depois de carregado
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cliente, campos, atrasoDaValidacaoMs]);

  // Salva o rascunho depois de uma pausa na edição (só de formulário existente).
  useEffect(() => {
    if (primeiraRenderizacao.current) {
      primeiraRenderizacao.current = false;
      return;
    }
    if (!formulario) return;
    const temporizador = setTimeout(() => {
      setStatusDoRascunho("salvando");
      cliente
        .salvarRascunho(
          formulario.id,
          paraDefinicao(campos, aceitas),
          revisaoDoRascunho.current ?? undefined,
        )
        .then(
          (salvo) => {
            revisaoDoRascunho.current = salvo.revisao;
            setTemRascunho(true);
            setStatusDoRascunho("salvo");
          },
          (erro: unknown) => {
            if (erro instanceof ErroDaApi && erro.status === 409) {
              setStatusDoRascunho("conflito");
              setFalha(erro.message);
            } else {
              setStatusDoRascunho("falhou");
            }
          },
        );
    }, 1500);
    return () => clearTimeout(temporizador);
    // `aceitas` deriva do catálogo, que não muda depois de carregado
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cliente, campos]);

  async function validar() {
    setValidando(true);
    setResultadoDaValidacao(null);
    const instantaneo = campos.map(({ chave, id }) => ({ chave, id }));
    try {
      const resultado = await cliente.validarDefinicao(paraDefinicao(campos, aceitas));
      setErros(mapearErros(resultado.erros, instantaneo));
      setResultadoDaValidacao(
        resultado.valida
          ? "Definição válida: pode publicar."
          : `${resultado.erros.length} ${resultado.erros.length === 1 ? "problema encontrado" : "problemas encontrados"}; veja nos campos.`,
      );
    } catch (erro) {
      setFalha(mensagemDe(erro));
    } finally {
      setValidando(false);
    }
  }

  async function descartarRascunho() {
    if (!formulario) return;
    try {
      await cliente.descartarRascunho(formulario.id);
      window.location.reload();
    } catch (erro) {
      setFalha(mensagemDe(erro));
    }
  }

  function aoPegar(evento: DragStartEvent) {
    setArrastado((evento.active.data.current as Arrastado | undefined) ?? null);
    setSobre(null);
  }

  function aoPassarPor(evento: DragOverEvent) {
    setSobre(evento.over ? String(evento.over.id) : null);
  }

  function limparArraste() {
    setArrastado(null);
    setSobre(null);
  }

  function aoSoltar(evento: DragEndEvent) {
    limparArraste();
    const solto = evento.active.data.current as Arrastado | undefined;
    if (!solto) return;
    const alvo = evento.over ? String(evento.over.id) : null;
    const depois = aplicarArraste(campos, solto, alvo, rotulosDosTipos, gerarChave);
    setCampos(depois);
    // Um tipo da paleta solto vira um campo novo: ele entra com animação e já fica selecionado,
    // como no "Adicionar campo".
    const nova = solto.origem === "paleta" ? chaveDoCampoNovo(campos, depois) : null;
    if (nova) {
      setRecemAdicionada(nova);
      setSelecionada(nova);
    }
  }

  function adicionar(tipo: TipoDeCampo) {
    const rotulo = rotulosDosTipos[tipo] ?? tipo;
    const novos = adicionarCampo(campos, tipo, rotulo, gerarChave);
    setCampos(novos);
    setSelecionada(novos[novos.length - 1]?.chave ?? null);
    setRecemAdicionada(novos[novos.length - 1]?.chave ?? null);
  }

  async function publicar() {
    setPublicando(true);
    setFalha(null);
    setErroDoNome([]);
    const instantaneo = campos.map(({ chave, id }) => ({ chave, id }));
    const definicao = paraDefinicao(campos, aceitas);
    try {
      if (formulario && revisaoDoRascunho.current !== null) {
        // Há rascunho da equipe: grava o que está na tela e publica a partir dele.
        const salvo = await cliente.salvarRascunho(
          formulario.id,
          definicao,
          revisaoDoRascunho.current,
        );
        revisaoDoRascunho.current = salvo.revisao;
        await cliente.publicarRascunho(formulario.id);
      } else if (formulario) {
        await cliente.publicarVersao(formulario.id, definicao);
      } else {
        const pastaId = modo.tipo === "novo" ? modo.pastaId : undefined;
        await cliente.criarFormulario(
          pastaId === undefined ? { nome, definicao } : { nome, definicao, pasta_id: pastaId },
        );
      }
      // Quem criou dentro de uma pasta volta para ela.
      navegar(
        modo.tipo === "novo" && modo.pastaId !== undefined
          ? { nome: "pasta", pastaId: modo.pastaId }
          : { nome: "formularios" },
      );
    } catch (erro) {
      if (erro instanceof ErroDaApi && erro.status === 422) {
        camposComErroDePublicacao.current = campos;
        setErroDoNome(erro.erros.filter((e) => e.campo === "nome").map((e) => e.mensagem));
        setErros(
          mapearErros(
            erro.erros.filter((e) => e.campo !== "nome"),
            instantaneo,
          ),
        );
      } else {
        setFalha(mensagemDe(erro));
      }
    } finally {
      setPublicando(false);
    }
  }

  const campoSelecionado = campos.find((campo) => campo.chave === selecionada) ?? null;

  // Os campos que cada origem compartilha viram `<referência>__<campo>` nas fórmulas (§2.7).
  const referencias = campos
    .filter((campo) => campo.tipo === "referencia" && campo.formulario.trim() !== "")
    .map((campo) => ({ id: campo.id, rotulo: campo.rotulo, formulario: campo.formulario.trim() }));
  const origens = useCamposDeOrigem(
    carregado.origensPossiveis,
    referencias.map((referencia) => referencia.formulario),
  );
  const camposDasReferencias = camposDeFormulaDasReferencias(referencias, origens);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto flex min-w-0 flex-col gap-1">
          {editando ? (
            <nav
              aria-label="Caminho"
              className="flex flex-wrap items-center gap-1 text-sm text-pedra-600"
            >
              <a href="#/formularios" className="hover:text-pedra-900">
                Formulários
              </a>
              {caminhoDaPasta(carregado.pastas, formulario.pasta_id ?? null).map((p) => (
                <span key={p.id} className="inline-flex items-center gap-1">
                  <Icone nome="seta" tamanho={12} />
                  <a href={`#/pastas/${p.id}`} className="hover:text-pedra-900">
                    {p.nome}
                  </a>
                </span>
              ))}
            </nav>
          ) : null}
          <h1 className="flex flex-wrap items-center gap-2 text-2xl font-extrabold">
            {editando ? formulario.nome : rascunho ? "Editar rascunho" : "Novo formulário"}
            {editando ? <Selo>rascunho da v{formulario.versao_atual.numero + 1}</Selo> : null}
          </h1>
          {editando ? (
            <p className="text-sm text-pedra-500" aria-live="polite">
              Os registros antigos continuam na versão deles.{" "}
              {statusDoRascunho === "salvando" ? "Salvando rascunho…" : null}
              {statusDoRascunho === "salvo" ? "Rascunho salvo para a equipe." : null}
              {statusDoRascunho === "falhou" ? "Não foi possível salvar o rascunho agora." : null}
            </p>
          ) : null}
        </div>
        {!editando ? (
          <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
            Nome do formulário
            <input
              type="text"
              className={CLASSE_DO_CONTROLE}
              value={nome}
              aria-invalid={erroDoNome.length > 0}
              onChange={(e) => setNome(e.target.value)}
            />
            {erroDoNome.map((mensagem) => (
              <span key={mensagem} role="alert" className="font-normal text-erro-700">
                {mensagem}
              </span>
            ))}
          </label>
        ) : null}
        {rascunho ? (
          <>
            <Botao onClick={rascunho.aoCancelar}>Cancelar</Botao>
            <Botao
              variante="primario"
              onClick={() => rascunho.aoConcluir(nome, paraDefinicao(campos, aceitas))}
            >
              Concluir edição
            </Botao>
          </>
        ) : (
          <>
            {!editando ? (
              <ComPermissao permissao="ia:criar_formularios" bloqueado="Criar com IA">
                <Botao onClick={() => navegar({ nome: "criarComIa" })}>
                  <Icone nome="brilho" />
                  Criar com IA
                </Botao>
              </ComPermissao>
            ) : null}
            {editando && temRascunho ? (
              <Botao variante="fantasma" onClick={() => void descartarRascunho()}>
                Descartar rascunho
              </Botao>
            ) : null}
            <Botao carregando={validando} onClick={() => void validar()}>
              Validar
            </Botao>
            <Botao variante="primario" carregando={publicando} onClick={() => void publicar()}>
              {publicando
                ? "Publicando…"
                : editando
                  ? `Publicar versão ${formulario.versao_atual.numero + 1}`
                  : "Publicar formulário"}
            </Botao>
          </>
        )}
      </div>
      {resultadoDaValidacao ? (
        <Aviso
          tom={
            erros.globais.length === 0 && Object.keys(erros.porCampo).length === 0
              ? "sucesso"
              : "erro"
          }
        >
          {resultadoDaValidacao}
        </Aviso>
      ) : null}
      {rascunho ? (
        <p className="text-sm text-pedra-500">
          A validação completa acontece ao publicar todos os rascunhos juntos, porque eles podem
          depender uns dos outros.
        </p>
      ) : null}

      {falha ? <Falha mensagem={falha} /> : null}
      {erros.globais.length > 0 ? <Falha mensagem={erros.globais.join(" · ")} /> : null}

      <DndContext
        sensors={sensores}
        onDragStart={aoPegar}
        onDragOver={aoPassarPor}
        onDragEnd={aoSoltar}
        onDragCancel={limparArraste}
        accessibility={{
          announcements: anunciosDoConstrutor({
            campos: () => campos,
            rotuloDoTipo: (tipo) => rotulosDosTipos[tipo] ?? tipo,
          }),
          screenReaderInstructions: { draggable: INSTRUCOES_DO_CONSTRUTOR },
        }}
      >
        <div className="grid gap-4 lg:grid-cols-[13rem_1fr_22rem]">
          <Paleta catalogo={catalogo} adicionar={adicionar} />
          <ListaDeCampos
            campos={campos}
            selecionada={selecionada}
            recemAdicionada={recemAdicionada}
            // O indicador só faz sentido ao trazer um tipo da paleta; reordenar já anima os vizinhos.
            indicador={arrastado?.origem === "paleta" ? posicaoDoDestino(campos, sobre) : null}
            arrastandoDaPaleta={arrastado?.origem === "paleta"}
            errosPorCampo={erros.porCampo}
            selecionar={setSelecionada}
            mover={(chave, posicao) => setCampos((atuais) => moverCampo(atuais, chave, posicao))}
            remover={(chave) => {
              setCampos((atuais) => removerCampo(atuais, chave));
              setSelecionada((atual) => (atual === chave ? null : atual));
            }}
          />
          {campoSelecionado ? (
            <PainelDePropriedades
              campo={campoSelecionado}
              todosOsCampos={campos}
              catalogo={catalogo}
              formulariosDeOrigem={carregado.nomesDosFormularios}
              camposDasReferencias={camposDasReferencias}
              erros={erros.porCampo[campoSelecionado.chave] ?? []}
              aoMudar={(mudancas) =>
                setCampos((atuais) => atualizarCampo(atuais, campoSelecionado.chave, mudancas))
              }
            />
          ) : (
            <p className="text-sm text-pedra-500">
              Selecione um campo para editar as propriedades.
            </p>
          )}
        </div>
        <DragOverlay dropAnimation={movimentoReduzido ? null : undefined}>
          {arrastado ? (
            <div className="flex items-center gap-2 rounded-cartao border border-sinal-500 bg-superficie px-3 py-2 text-sm font-medium shadow-elevada">
              <Icone
                nome={arrastado.origem === "paleta" ? "mais" : "alca"}
                className="text-sinal-600"
              />
              {arrastado.origem === "paleta"
                ? (rotulosDosTipos[arrastado.tipo] ?? arrastado.tipo)
                : campos.find((c) => c.chave === arrastado.chave)?.rotulo || "(sem rótulo)"}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </section>
  );
}

/** Da raiz até a pasta do formulário, para o cabeçalho. */
function caminhoDaPasta(pastas: Pasta[], pastaId: number | null): Pasta[] {
  const caminho: Pasta[] = [];
  let atual = pastas.find((p) => p.id === pastaId);
  while (atual && caminho.length < 20) {
    caminho.unshift(atual);
    const paiId: number | null = atual.pasta_pai_id;
    atual = paiId === null ? undefined : pastas.find((p) => p.id === paiId);
  }
  return caminho;
}

function Paleta({
  catalogo,
  adicionar,
}: {
  catalogo: Catalogo;
  adicionar: (tipo: TipoDeCampo) => void;
}) {
  return (
    <section aria-label="Tipos de campo" className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Tipos de campo</h2>
      <ul className="flex flex-col gap-1">
        {catalogo.tipos.map((tipo) => (
          <ItemDaPaleta
            key={tipo.id}
            tipo={tipo.id as TipoDeCampo}
            rotulo={tipo.rotulo}
            adicionar={adicionar}
          />
        ))}
      </ul>
    </section>
  );
}

function ItemDaPaleta({
  tipo,
  rotulo,
  adicionar,
}: {
  tipo: TipoDeCampo;
  rotulo: string;
  adicionar: (tipo: TipoDeCampo) => void;
}) {
  // Sem `transform`: quem se move com o ponteiro é o `DragOverlay`; este item fica no lugar,
  // apagado, como "fantasma" da origem.
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `paleta-${tipo}`,
    data: { origem: "paleta", tipo } satisfies Arrastado,
  });
  return (
    <li
      ref={setNodeRef}
      className={`flex items-center gap-1 rounded-controle border bg-superficie transition-opacity duration-(--duracao-rapida) ${
        isDragging ? "border-dashed border-sinal-300 opacity-45" : "border-pedra-200"
      }`}
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Arrastar o tipo ${rotulo}`}
        className="grid size-8 shrink-0 cursor-grab touch-none place-items-center rounded-controle text-pedra-400 hover:text-pedra-700 active:cursor-grabbing"
      >
        <Icone nome="alca" />
      </span>
      <button
        type="button"
        className="flex-1 py-1.5 text-left"
        aria-label={`Adicionar campo ${rotulo}`}
        onClick={() => adicionar(tipo)}
      >
        {rotulo}
      </button>
    </li>
  );
}

function ListaDeCampos({
  campos,
  selecionada,
  recemAdicionada,
  indicador,
  arrastandoDaPaleta,
  errosPorCampo,
  selecionar,
  mover,
  remover,
}: {
  campos: CampoEmEdicao[];
  selecionada: string | null;
  recemAdicionada: string | null;
  /** A posição (0 a n) em que o tipo arrastado entraria; `null` quando não há destino. */
  indicador: number | null;
  arrastandoDaPaleta: boolean;
  errosPorCampo: ErrosMapeados["porCampo"];
  selecionar: (chave: string) => void;
  mover: (chave: string, posicao: number) => void;
  remover: (chave: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: AREA_DA_LISTA });
  return (
    <section aria-label="Campos do formulário" className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Campos</h2>
      <div
        ref={setNodeRef}
        className={`min-h-32 rounded-cartao border-2 border-dashed p-2 transition-colors duration-(--duracao-rapida) ${
          isOver || arrastandoDaPaleta ? "border-sinal-300 bg-sinal-100/40" : "border-pedra-200"
        }`}
      >
        {campos.length === 0 && indicador === null ? (
          <p className="p-4 text-center text-sm text-pedra-500">
            Arraste um tipo para cá ou use “Adicionar campo”.
          </p>
        ) : null}
        <SortableContext items={campos.map((c) => c.chave)} strategy={verticalListSortingStrategy}>
          <ol className="flex flex-col gap-2">
            {campos.map((campo, indice) => (
              <Fragment key={campo.chave}>
                {indicador === indice ? <IndicadorDeDestino /> : null}
                <ItemDoCampo
                  entrando={campo.chave === recemAdicionada}
                  campo={campo}
                  selecionado={campo.chave === selecionada}
                  quantidadeDeErros={errosPorCampo[campo.chave]?.length ?? 0}
                  primeiro={indice === 0}
                  ultimo={indice === campos.length - 1}
                  selecionar={() => selecionar(campo.chave)}
                  moverPara={(posicao) => mover(campo.chave, posicao)}
                  posicao={indice}
                  remover={() => remover(campo.chave)}
                />
              </Fragment>
            ))}
            {indicador === campos.length ? <IndicadorDeDestino /> : null}
          </ol>
        </SortableContext>
      </div>
    </section>
  );
}

/** A linha que mostra onde o tipo arrastado vai entrar. */
function IndicadorDeDestino() {
  return (
    <li aria-hidden="true" className="relative h-0.5 rounded-full bg-sinal-500">
      <span className="absolute -left-1 -top-[3px] size-2 rounded-full bg-sinal-500" />
    </li>
  );
}

function ItemDoCampo({
  entrando,
  campo,
  selecionado,
  quantidadeDeErros,
  primeiro,
  ultimo,
  posicao,
  selecionar,
  moverPara,
  remover,
}: {
  entrando: boolean;
  campo: CampoEmEdicao;
  selecionado: boolean;
  quantidadeDeErros: number;
  primeiro: boolean;
  ultimo: boolean;
  posicao: number;
  selecionar: () => void;
  moverPara: (posicao: number) => void;
  remover: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: campo.chave,
    data: { origem: "campo", chave: campo.chave } satisfies Arrastado,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 rounded-controle border bg-superficie p-2 ${
        entrando ? "animate-entrar" : ""
      } ${isDragging ? "border-dashed border-sinal-300 opacity-45" : ""} ${
        selecionado ? "border-pedra-900" : "border-pedra-200"
      } ${quantidadeDeErros > 0 ? "border-erro-300" : ""}`}
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Arrastar o campo ${campo.rotulo}`}
        className="grid size-8 shrink-0 cursor-grab touch-none place-items-center rounded-controle text-pedra-400 hover:text-pedra-700 active:cursor-grabbing"
      >
        <Icone nome="alca" />
      </span>
      <button
        type="button"
        className="flex-1 text-left"
        aria-pressed={selecionado}
        aria-label={`Selecionar o campo ${campo.rotulo}`}
        onClick={selecionar}
      >
        <span className="font-medium">{campo.rotulo || "(sem rótulo)"}</span>{" "}
        <span className="font-mono text-xs text-pedra-500">
          {campo.id || "(sem id)"} · {campo.tipo}
        </span>
        {quantidadeDeErros > 0 ? (
          <span className="ml-2 text-sm text-erro-700">{quantidadeDeErros} erro(s)</span>
        ) : null}
      </button>
      <button
        type="button"
        className="px-1 disabled:opacity-30"
        aria-label={`Mover ${campo.rotulo} para cima`}
        disabled={primeiro}
        onClick={() => moverPara(posicao - 1)}
      >
        ↑
      </button>
      <button
        type="button"
        className="px-1 disabled:opacity-30"
        aria-label={`Mover ${campo.rotulo} para baixo`}
        disabled={ultimo}
        onClick={() => moverPara(posicao + 1)}
      >
        ↓
      </button>
      <button
        type="button"
        className="px-1 text-erro-700"
        aria-label={`Remover o campo ${campo.rotulo}`}
        onClick={remover}
      >
        ×
      </button>
    </li>
  );
}
