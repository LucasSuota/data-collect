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
} from "@dnd-kit/core";
import {
  SortableContext,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState, type KeyboardEvent } from "react";
import type { Esquemas } from "../api/cliente";
import { useMovimentoReduzido } from "../lib/movimentoReduzido";
import { Aviso, Botao, Icone } from "../ui";
import {
  ID_DO_FIM,
  PREFIXO_DE_ITEM,
  blocoDe,
  blocosDaFuncao,
  idDoBloco,
  inserirBlocos,
  lexar,
  moverBloco,
  paraTexto,
  paresDeBlocos,
  removerBloco,
  resolverSolto,
  type Bloco,
} from "./blocos";

type FuncaoDoCatalogo = Esquemas["FuncaoDoCatalogoSaida"];

interface Props {
  valor: string;
  aoMudar: (valor: string) => void;
  funcoes: FuncaoDoCatalogo[];
  constantes: string[];
  campos: { id: string; rotulo: string }[];
  erro?: { mensagem: string; posicao?: { inicio: number; fim: number } | null } | undefined;
}

/** O que a paleta oferece: um texto simples (campo, operador...) ou uma função (entra com `()`). */
type Item = { tipo: "texto"; texto: string } | { tipo: "funcao"; nome: string };

const OPERADORES = ["+", "-", "*", "/", "**", "==", "!=", "<", "<=", ">", ">=", "and", "or", "not"];
const NUMERO_VALIDO = /^(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?$/;

const ROTULO_DO_BLOCO: Record<Bloco["tipo"], (texto: string) => string> = {
  campo: (t) => `campo ${t}`,
  numero: (t) => `número ${t}`,
  operador: (t) => `operador ${t}`,
  funcao: (t) => `função ${t}`,
  constante: (t) => `constante ${t}`,
  abre: () => "parêntese que abre",
  fecha: () => "parêntese que fecha",
  virgula: () => "vírgula",
  outro: (t) => `sem tipo ${t}`,
};

/** A cor de cada tipo de bloco. Fundo e borda vêm juntos para nunca disputarem com o destaque. */
const COR_DO_BLOCO: Record<Bloco["tipo"], string> = {
  campo: "border-transparent bg-pedra-200 text-pedra-900 font-mono",
  numero: "border-pedra-300 bg-superficie text-pedra-900 font-mono",
  operador: "border-pedra-300 bg-superficie text-pedra-700 font-mono",
  funcao: "border-transparent bg-pedra-900 text-superficie font-mono",
  constante: "border-transparent bg-pedra-100 text-pedra-800 font-mono italic",
  abre: "border-transparent bg-pedra-100 text-pedra-700 font-mono",
  fecha: "border-transparent bg-pedra-100 text-pedra-700 font-mono",
  virgula: "border-transparent bg-transparent text-pedra-500 font-mono",
  outro: "border-aviso-300 bg-aviso-50 text-aviso-700 font-mono",
};

/** O destaque (erro do servidor, parêntese sem par, par do cursor) substitui a cor do tipo. */
const COR_DE_DESTAQUE = {
  erro: "border-erro-300 bg-erro-50 text-erro-700 font-mono",
  semPar: "border-aviso-300 bg-aviso-50 text-aviso-700 font-mono",
  par: "border-sinal-500 bg-sinal-100 text-pedra-900 font-mono",
} as const;

function blocosDoItem(item: Item, constantes: string[]): { blocos: Bloco[]; cursor: number } {
  if (item.tipo === "funcao") return blocosDaFuncao(item.nome);
  const blocos = blocoDe(item.texto, constantes);
  return { blocos, cursor: blocos.length };
}

/**
 * Monta a fórmula com blocos: clicar ou arrastar itens da paleta, reordenar e remover. Os blocos
 * são só fichas léxicas do texto (veja `blocos.ts`); aqui não há gramática, e quem valida e calcula
 * é o servidor. O texto só muda quando se edita um bloco.
 */
export function EditorDeBlocos({ valor, aoMudar, funcoes, constantes, campos, erro }: Props) {
  const blocos = lexar(valor, constantes);
  const [cursor, setCursor] = useState(blocos.length);
  const [arrastado, setArrastado] = useState<string | null>(null);
  const [numero, setNumero] = useState("");
  const movimentoReduzido = useMovimentoReduzido();
  const sensores = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const posicao = Math.min(cursor, blocos.length);
  const { pares, semPar } = paresDeBlocos(blocos);
  const parDoCursor = pares.find(([abre, fecha]) =>
    [posicao - 1, posicao].some((i) => i === abre || i === fecha),
  );
  const semBloco = [...new Set(blocos.filter((b) => b.tipo === "outro").map((b) => b.texto))];

  function aplicar(novos: Bloco[], novoCursor: number) {
    setCursor(novoCursor);
    aoMudar(paraTexto(novos));
  }

  function inserirItem(item: Item, em: number = posicao) {
    const { blocos: novos, cursor: dentro } = blocosDoItem(item, constantes);
    aplicar(inserirBlocos(blocos, em, novos), em + dentro);
  }

  function aoSoltar(evento: DragEndEvent) {
    setArrastado(null);
    const solto = resolverSolto(
      String(evento.active.id),
      evento.over ? String(evento.over.id) : null,
      blocos.length,
    );
    if (!solto) return;
    if (solto.tipo === "mover") {
      aplicar(moverBloco(blocos, solto.de, solto.para), solto.para + 1);
      return;
    }
    const item = evento.active.data.current?.["item"] as Item | undefined;
    if (item) inserirItem(item, solto.posicao);
  }

  function aoTeclarNoBloco(evento: KeyboardEvent, indice: number) {
    if (evento.key === "Delete" || evento.key === "Backspace") {
      evento.preventDefault();
      aplicar(removerBloco(blocos, indice), indice);
    } else if (evento.altKey && (evento.key === "ArrowLeft" || evento.key === "ArrowRight")) {
      evento.preventDefault();
      const para = indice + (evento.key === "ArrowLeft" ? -1 : 1);
      if (para >= 0 && para < blocos.length) aplicar(moverBloco(blocos, indice, para), para + 1);
    }
  }

  const textoDoArrastado =
    arrastado === null
      ? null
      : arrastado.startsWith(PREFIXO_DE_ITEM)
        ? arrastado.slice(PREFIXO_DE_ITEM.length).replace(/^[a-z]+-/, "")
        : (blocos[Number(arrastado.replace("bloco-", ""))]?.texto ?? null);

  return (
    <DndContext
      sensors={sensores}
      onDragStart={(evento) => setArrastado(String(evento.active.id))}
      onDragEnd={aoSoltar}
      onDragCancel={() => setArrastado(null)}
      accessibility={{
        screenReaderInstructions: {
          draggable:
            "Para arrastar, pressione espaço, use as setas e pressione espaço de novo para soltar. " +
            "Também funciona Alt com as setas para mover um bloco e Delete para removê-lo.",
        },
      }}
    >
      <div className="flex flex-col gap-3">
        <Faixa
          blocos={blocos}
          posicao={posicao}
          erro={erro}
          semPar={semPar}
          parDoCursor={parDoCursor}
          irPara={setCursor}
          remover={(indice) => aplicar(removerBloco(blocos, indice), indice)}
          aoTeclar={aoTeclarNoBloco}
        />

        {semBloco.length > 0 ? (
          <Aviso tom="info">
            Há trechos sem bloco ({semBloco.join(" ")}): ficam como estão. Edite-os no modo texto.
          </Aviso>
        ) : null}

        <PaletaDeBlocos
          funcoes={funcoes}
          constantes={constantes}
          campos={campos}
          inserir={inserirItem}
          numero={numero}
          mudarNumero={setNumero}
          inserirNumero={() => {
            inserirItem({ tipo: "texto", texto: numero });
            setNumero("");
          }}
        />
      </div>
      <DragOverlay dropAnimation={movimentoReduzido ? null : undefined}>
        {textoDoArrastado ? (
          <span className="rounded-controle border border-sinal-500 bg-superficie px-2 py-1 font-mono text-sm shadow-elevada">
            {textoDoArrastado}
          </span>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

interface PropriedadesDaPaleta {
  funcoes: FuncaoDoCatalogo[];
  constantes: string[];
  campos: { id: string; rotulo: string }[];
  inserir: (item: Item) => void;
  numero: string;
  mudarNumero: (valor: string) => void;
  inserirNumero: () => void;
}

function Faixa({
  blocos,
  posicao,
  erro,
  semPar,
  parDoCursor,
  irPara,
  remover,
  aoTeclar,
}: {
  blocos: Bloco[];
  posicao: number;
  erro: Props["erro"];
  semPar: number[];
  parDoCursor: [number, number] | undefined;
  irPara: (posicao: number) => void;
  remover: (indice: number) => void;
  aoTeclar: (evento: KeyboardEvent, indice: number) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: ID_DO_FIM });
  const erroDoServidor = erro?.posicao ?? null;

  return (
    <div className="flex flex-col gap-2">
      <ol
        ref={setNodeRef}
        aria-label="Fórmula em blocos"
        className={`flex min-h-14 flex-wrap items-center gap-y-2 rounded-cartao border-2 border-dashed p-2 transition-colors duration-(--duracao-rapida) ${
          isOver ? "border-sinal-300 bg-sinal-100/40" : "border-pedra-200"
        }`}
      >
        {blocos.length === 0 ? (
          <li className="px-2 text-sm text-pedra-500">
            Escolha um bloco na paleta ou arraste-o para cá.
          </li>
        ) : null}
        <SortableContext
          items={blocos.map((_, i) => idDoBloco(i))}
          strategy={horizontalListSortingStrategy}
        >
          <li className="list-none">
            <Cursor rotulo="Cursor no início" ativo={posicao === 0} aoClicar={() => irPara(0)} />
          </li>
          {blocos.map((bloco, indice) => (
            <ItemDoBloco
              key={indice}
              bloco={bloco}
              indice={indice}
              cursorDepois={posicao === indice + 1}
              comErro={
                erroDoServidor !== null &&
                bloco.inicio < erroDoServidor.fim &&
                bloco.fim > erroDoServidor.inicio
              }
              semPar={semPar.includes(indice)}
              doPar={parDoCursor?.includes(indice) ?? false}
              irPara={irPara}
              remover={() => remover(indice)}
              aoTeclar={(e) => aoTeclar(e, indice)}
            />
          ))}
        </SortableContext>
      </ol>
      {erro ? (
        <p role="alert" className="text-sm text-erro-700">
          {erro.mensagem}
        </p>
      ) : null}
    </div>
  );
}

function Cursor({
  rotulo,
  ativo,
  aoClicar,
}: {
  rotulo: string;
  ativo: boolean;
  aoClicar: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={rotulo}
      aria-pressed={ativo}
      tabIndex={-1}
      onClick={aoClicar}
      className="group grid h-7 w-2.5 place-items-center"
    >
      <span
        className={`h-6 w-0.5 rounded-full transition-colors duration-(--duracao-rapida) ${
          ativo ? "bg-sinal-500" : "bg-transparent group-hover:bg-pedra-300"
        }`}
      />
    </button>
  );
}

function ItemDoBloco({
  bloco,
  indice,
  cursorDepois,
  comErro,
  semPar,
  doPar,
  irPara,
  remover,
  aoTeclar,
}: {
  bloco: Bloco;
  indice: number;
  cursorDepois: boolean;
  comErro: boolean;
  semPar: boolean;
  doPar: boolean;
  irPara: (posicao: number) => void;
  remover: () => void;
  aoTeclar: (evento: KeyboardEvent) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: idDoBloco(indice),
  });
  const rotulo = ROTULO_DO_BLOCO[bloco.tipo](bloco.texto);
  const cor = comErro
    ? COR_DE_DESTAQUE.erro
    : semPar
      ? COR_DE_DESTAQUE.semPar
      : doPar
        ? COR_DE_DESTAQUE.par
        : COR_DO_BLOCO[bloco.tipo];

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center ${isDragging ? "opacity-45" : ""}`}
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Bloco ${rotulo}`}
        data-erro={comErro ? "true" : undefined}
        data-sem-par={semPar ? "true" : undefined}
        className={`group/bloco inline-flex min-h-7 cursor-grab touch-none items-center gap-1 rounded-controle border px-2 text-sm active:cursor-grabbing ${cor}`}
        onClick={() => irPara(indice + 1)}
        onKeyDown={(evento) => {
          aoTeclar(evento);
          listeners?.["onKeyDown"]?.(evento);
        }}
      >
        {bloco.texto}
        <button
          type="button"
          aria-label={`Remover o bloco ${bloco.texto}`}
          tabIndex={-1}
          className="grid size-4 place-items-center rounded-sm opacity-0 hover:bg-black/10 group-hover/bloco:opacity-100 group-focus/bloco:opacity-100"
          onClick={(evento) => {
            evento.stopPropagation();
            remover();
          }}
        >
          ×
        </button>
      </span>
      <Cursor
        rotulo={`Cursor depois de ${bloco.texto}`}
        ativo={cursorDepois}
        aoClicar={() => irPara(indice + 1)}
      />
    </li>
  );
}

function PaletaDeBlocos({
  funcoes,
  constantes,
  campos,
  inserir,
  numero,
  mudarNumero,
  inserirNumero,
}: PropriedadesDaPaleta) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      <Grupo titulo="Campos">
        {campos.map((campo) => (
          <ItemDaPaleta
            key={campo.id}
            chave={`campo-${campo.id}`}
            item={{ tipo: "texto", texto: campo.id }}
            rotulo={`Inserir o campo ${campo.id}`}
            titulo={campo.rotulo}
            inserir={inserir}
          >
            {campo.id}
          </ItemDaPaleta>
        ))}
      </Grupo>
      <Grupo titulo="Funções">
        {funcoes.map((funcao) => (
          <ItemDaPaleta
            key={funcao.nome}
            chave={`funcao-${funcao.nome}`}
            item={{ tipo: "funcao", nome: funcao.nome }}
            rotulo={`Inserir a função ${funcao.nome}`}
            titulo={`${funcao.assinatura}: ${funcao.descricao}`}
            inserir={inserir}
          >
            {funcao.nome}()
          </ItemDaPaleta>
        ))}
      </Grupo>
      <Grupo titulo="Operadores">
        {OPERADORES.map((operador) => (
          <ItemDaPaleta
            key={operador}
            chave={`operador-${operador}`}
            item={{ tipo: "texto", texto: operador }}
            rotulo={`Inserir o operador ${operador}`}
            inserir={inserir}
          >
            {operador}
          </ItemDaPaleta>
        ))}
      </Grupo>
      <Grupo titulo="Parênteses, vírgula e constantes">
        <ItemDaPaleta
          chave="abre"
          item={{ tipo: "texto", texto: "(" }}
          rotulo="Inserir o parêntese que abre"
          inserir={inserir}
        >
          (
        </ItemDaPaleta>
        <ItemDaPaleta
          chave="fecha"
          item={{ tipo: "texto", texto: ")" }}
          rotulo="Inserir o parêntese que fecha"
          inserir={inserir}
        >
          )
        </ItemDaPaleta>
        <ItemDaPaleta
          chave="virgula"
          item={{ tipo: "texto", texto: "," }}
          rotulo="Inserir a vírgula"
          inserir={inserir}
        >
          ,
        </ItemDaPaleta>
        {constantes.map((constante) => (
          <ItemDaPaleta
            key={constante}
            chave={`constante-${constante}`}
            item={{ tipo: "texto", texto: constante }}
            rotulo={`Inserir a constante ${constante}`}
            inserir={inserir}
          >
            {constante}
          </ItemDaPaleta>
        ))}
      </Grupo>
      <div className="flex items-end gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
          Número
          <input
            value={numero}
            inputMode="decimal"
            className="min-h-7 w-28 rounded-controle border border-pedra-300 bg-superficie px-2 font-mono text-sm"
            onChange={(evento) => mudarNumero(evento.target.value)}
            onKeyDown={(evento) => {
              if (evento.key === "Enter" && NUMERO_VALIDO.test(numero.trim())) {
                evento.preventDefault();
                inserirNumero();
              }
            }}
          />
        </label>
        <Botao
          tamanho="pequeno"
          disabled={!NUMERO_VALIDO.test(numero.trim())}
          aria-label="Inserir o número"
          onClick={inserirNumero}
        >
          <Icone nome="mais" />
          Inserir
        </Botao>
      </div>
    </div>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="mb-1.5 font-medium text-pedra-600">{titulo}</legend>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </fieldset>
  );
}

/** Um item da paleta: o botão insere no cursor; a alça ao lado arrasta para a posição que se quiser. */
function ItemDaPaleta({
  chave,
  item,
  rotulo,
  titulo,
  inserir,
  children,
}: {
  chave: string;
  item: Item;
  rotulo: string;
  titulo?: string;
  inserir: (item: Item) => void;
  children: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `${PREFIXO_DE_ITEM}${chave}`,
    data: { item },
  });
  return (
    <span
      ref={setNodeRef}
      className={`inline-flex items-center rounded-controle border border-pedra-300 bg-superficie transition-opacity duration-(--duracao-rapida) ${
        isDragging ? "opacity-45" : ""
      }`}
    >
      <span
        {...attributes}
        {...listeners}
        aria-label={`Arrastar ${chave.replace(/^[a-z]+-/, "")}`}
        className="grid size-7 cursor-grab touch-none place-items-center text-pedra-400 hover:text-pedra-700 active:cursor-grabbing"
      >
        <Icone nome="alca" tamanho={14} />
      </span>
      <button
        type="button"
        title={titulo}
        aria-label={rotulo}
        className="min-h-7 rounded-r-controle pr-2 font-mono text-[0.8125rem] hover:bg-pedra-100"
        onClick={() => inserir(item)}
      >
        {children}
      </button>
    </span>
  );
}
