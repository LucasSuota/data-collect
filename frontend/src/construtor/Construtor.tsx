import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useEffect, useRef, useState } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi, type Esquemas, type FormularioDetalhe, type TipoDeCampo } from "../api/cliente";
import type { Rascunho } from "../ia/rascunhos";
import { EsqueletoDoConstrutor } from "../paginas/esqueletos";
import { Falha, mensagemDe, useCarga } from "../paginas/Estado";
import type { Rota } from "../rotas";
import { PainelDePropriedades } from "./PainelDePropriedades";
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
  formulario: FormularioDetalhe | null;
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
    const [catalogo, formularios, formulario] = await Promise.all([
      cliente.catalogo(),
      cliente.listarFormularios(),
      modo.tipo === "editar" ? cliente.obterFormulario(modo.formularioId) : Promise.resolve(null),
    ]);
    return {
      catalogo,
      nomesDosFormularios: [
        ...new Set([
          ...formularios
            .filter((f) => f.id !== formulario?.id) // o formulário não pode se referenciar
            .map((f) => f.nome),
          ...(modo.tipo === "rascunho" ? modo.nomesDosIrmaos : []),
        ]),
      ],
      formulario,
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
    if (formulario) return deDefinicao(formulario.versao_atual.definicao, gerarChave);
    return rascunho ? deRascunho(rascunho.rascunho.definicao, gerarChave) : [];
  });
  const [selecionada, setSelecionada] = useState<string | null>(null);
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

  function aoSoltar(evento: DragEndEvent) {
    const arrastado = evento.active.data.current as Arrastado | undefined;
    if (!arrastado) return;
    const alvo = evento.over ? String(evento.over.id) : null;
    setCampos((atuais) => aplicarArraste(atuais, arrastado, alvo, rotulosDosTipos, gerarChave));
  }

  function adicionar(tipo: TipoDeCampo) {
    const rotulo = rotulosDosTipos[tipo] ?? tipo;
    const novos = adicionarCampo(campos, tipo, rotulo, gerarChave);
    setCampos(novos);
    setSelecionada(novos[novos.length - 1]?.chave ?? null);
  }

  async function publicar() {
    setPublicando(true);
    setFalha(null);
    setErroDoNome([]);
    const instantaneo = campos.map(({ chave, id }) => ({ chave, id }));
    const definicao = paraDefinicao(campos, aceitas);
    try {
      if (formulario) {
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

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-2xl font-semibold">
          {editando
            ? `Editar · ${formulario.nome}`
            : rascunho
              ? "Editar rascunho"
              : "Novo formulário"}
        </h1>
        {editando ? (
          <p className="text-sm text-pedra-500">
            Publicar cria a versão {formulario.versao_atual.numero + 1}; os registros antigos
            continuam na versão deles.
          </p>
        ) : (
          <label className="flex flex-col text-sm font-medium">
            Nome do formulário
            <input
              type="text"
              className="rounded border border-pedra-300 px-2 py-1.5"
              value={nome}
              aria-invalid={erroDoNome.length > 0}
              onChange={(e) => setNome(e.target.value)}
            />
            {erroDoNome.map((mensagem) => (
              <span key={mensagem} role="alert" className="font-normal text-red-700">
                {mensagem}
              </span>
            ))}
          </label>
        )}
        {rascunho ? (
          <>
            <button
              type="button"
              className="rounded border border-pedra-300 px-4 py-2"
              onClick={rascunho.aoCancelar}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="rounded bg-pedra-900 px-4 py-2 text-white"
              onClick={() => rascunho.aoConcluir(nome, paraDefinicao(campos, aceitas))}
            >
              Concluir edição
            </button>
          </>
        ) : (
          <>
            {!editando ? (
              <button
                type="button"
                className="rounded border border-pedra-300 px-4 py-2"
                onClick={() => navegar({ nome: "criarComIa" })}
              >
                Criar com IA
              </button>
            ) : null}
            <button
              type="button"
              disabled={publicando}
              className="rounded bg-pedra-900 px-4 py-2 text-white disabled:opacity-60"
              onClick={() => void publicar()}
            >
              {publicando
                ? "Publicando…"
                : editando
                  ? "Publicar nova versão"
                  : "Publicar formulário"}
            </button>
          </>
        )}
      </div>
      {rascunho ? (
        <p className="text-sm text-pedra-500">
          A validação completa acontece ao publicar todos os rascunhos juntos, porque eles podem
          depender uns dos outros.
        </p>
      ) : null}

      {falha ? <Falha mensagem={falha} /> : null}
      {erros.globais.length > 0 ? <Falha mensagem={erros.globais.join(" · ")} /> : null}

      <DndContext sensors={sensores} onDragEnd={aoSoltar}>
        <div className="grid gap-4 md:grid-cols-[13rem_1fr_22rem]">
          <Paleta catalogo={catalogo} adicionar={adicionar} />
          <ListaDeCampos
            campos={campos}
            selecionada={selecionada}
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
      </DndContext>
    </section>
  );
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
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: `paleta-${tipo}`,
    data: { origem: "paleta", tipo } satisfies Arrastado,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform) }}
      className="flex items-center gap-1 rounded border border-pedra-200 bg-white"
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Arrastar o tipo ${rotulo}`}
        className="cursor-grab px-2 text-pedra-400"
      >
        ⠿
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
  errosPorCampo,
  selecionar,
  mover,
  remover,
}: {
  campos: CampoEmEdicao[];
  selecionada: string | null;
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
        className={`min-h-32 rounded border-2 border-dashed p-2 ${isOver ? "border-pedra-500" : "border-pedra-200"}`}
      >
        {campos.length === 0 ? (
          <p className="p-4 text-center text-sm text-pedra-500">
            Arraste um tipo para cá ou use “Adicionar campo”.
          </p>
        ) : null}
        <SortableContext items={campos.map((c) => c.chave)} strategy={verticalListSortingStrategy}>
          <ol className="flex flex-col gap-2">
            {campos.map((campo, indice) => (
              <ItemDoCampo
                key={campo.chave}
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
            ))}
          </ol>
        </SortableContext>
      </div>
    </section>
  );
}

function ItemDoCampo({
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
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: campo.chave,
    data: { origem: "campo", chave: campo.chave } satisfies Arrastado,
  });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 rounded border bg-white p-2 ${
        selecionado ? "border-pedra-900" : "border-pedra-200"
      } ${quantidadeDeErros > 0 ? "border-red-400" : ""}`}
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Arrastar o campo ${campo.rotulo}`}
        className="cursor-grab px-1 text-pedra-400"
      >
        ⠿
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
          <span className="ml-2 text-sm text-red-700">{quantidadeDeErros} erro(s)</span>
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
        className="px-1 text-red-700"
        aria-label={`Remover o campo ${campo.rotulo}`}
        onClick={remover}
      >
        ×
      </button>
    </li>
  );
}
