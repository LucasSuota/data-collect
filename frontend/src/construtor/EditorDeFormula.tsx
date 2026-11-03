import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Esquemas } from "../api/cliente";
import {
  analisarParenteses,
  aoApagar,
  aoDigitar,
  argumentoAtivo,
  argumentosDaAssinatura,
  chamadaNoCursor,
  parDoCursor,
  type Edicao,
} from "./formulaTexto";
import { EditorDeBlocos } from "./EditorDeBlocos";

type FuncaoDoCatalogo = Esquemas["FuncaoDoCatalogoSaida"];

interface Props {
  id: string;
  rotulo: string;
  valor: string;
  aoMudar: (valor: string) => void;
  /** Vêm do `GET /catalogo`: o front não conhece a gramática (AGENTS.md §5.3). */
  funcoes: FuncaoDoCatalogo[];
  constantes: string[];
  /** Campos que a fórmula pode usar (id e rótulo). */
  campos: { id: string; rotulo: string }[];
  /** O erro do servidor; `posicao` são offsets em caracteres no texto enviado. */
  erro?: { mensagem: string; posicao?: { inicio: number; fim: number } | null } | undefined;
}

const FIM_DA_PALAVRA = /[A-Za-z_][A-Za-z0-9_]*$/;

/**
 * Edita a fórmula com ajuda: autocompletar por teclado, dica da função com o argumento atual,
 * parênteses pareados e o trecho do erro sublinhado. Nenhum parse de fórmula aqui (só parênteses
 * e vírgulas, para ajudar a digitar): o servidor valida e diz onde está o erro.
 */
export function EditorDeFormula({
  id,
  rotulo,
  valor,
  aoMudar,
  funcoes,
  constantes,
  campos,
  erro,
}: Props) {
  const idDoErro = useId();
  const idDaLista = useId();
  const campo = useRef<HTMLTextAreaElement>(null);
  const cursorPendente = useRef<number | null>(null);
  const [cursor, setCursor] = useState(valor.length);
  const [ativa, setAtiva] = useState<number | null>(null);
  const [fechada, setFechada] = useState(false);
  // O texto é a fonte única; os blocos são só outra forma de editá-lo.
  const [modo, setModo] = useState<"texto" | "blocos">("texto");

  // Depois de uma edição feita por aqui (par de parênteses, sugestão), devolve o cursor ao lugar
  // certo: o `<textarea>` controlado o jogaria para o fim ao receber o valor novo.
  useLayoutEffect(() => {
    if (cursorPendente.current === null) return;
    campo.current?.setSelectionRange(cursorPendente.current, cursorPendente.current);
    cursorPendente.current = null;
  });

  const sugestoes = fechada ? [] : sugerir(valor.slice(0, cursor), funcoes, constantes, campos);
  const aberta = sugestoes.length > 0;
  const chamada = chamadaNoCursor(valor, cursor);
  const funcaoDaDica = chamada
    ? funcoes.find((f) => f.nome.toLowerCase() === chamada.nome.toLowerCase())
    : undefined;

  function aplicar(edicao: Edicao) {
    cursorPendente.current = edicao.cursor;
    setCursor(edicao.cursor);
    setAtiva(null);
    setFechada(false);
    if (edicao.texto !== valor) aoMudar(edicao.texto);
  }

  function inserir(texto: string, substituindoAPalavra: boolean) {
    const antes = valor.slice(0, cursor);
    const base = substituindoAPalavra ? antes.replace(FIM_DA_PALAVRA, "") : antes;
    aplicar({ texto: base + texto + valor.slice(cursor), cursor: (base + texto).length });
  }

  function aoTeclar(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (aberta) {
      if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
        evento.preventDefault();
        const passo = evento.key === "ArrowDown" ? 1 : -1;
        const inicio = ativa ?? (passo === 1 ? -1 : 0);
        setAtiva((inicio + passo + sugestoes.length) % sugestoes.length);
        return;
      }
      const escolhida = ativa === null ? undefined : sugestoes[ativa];
      if ((evento.key === "Enter" || evento.key === "Tab") && escolhida) {
        evento.preventDefault();
        inserir(escolhida.inserir, true);
        return;
      }
      if (evento.key === "Escape") {
        evento.preventDefault();
        setFechada(true);
        setAtiva(null);
        return;
      }
    }

    const { selectionStart: inicio, selectionEnd: fim } = evento.currentTarget;
    const edicao =
      evento.key === "Backspace" && inicio === fim
        ? aoApagar(valor, inicio)
        : aoDigitar(valor, inicio, fim, evento.key);
    if (edicao) {
      evento.preventDefault();
      aplicar(edicao);
    }
  }

  const par = parDoCursor(valor, cursor);
  const { semPar } = analisarParenteses(valor);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        {modo === "texto" ? (
          <label htmlFor={id} className="text-sm font-medium text-pedra-700">
            {rotulo}
          </label>
        ) : (
          <span className="text-sm font-medium text-pedra-700">{rotulo}</span>
        )}
        <div
          role="group"
          aria-label="Modo de edição"
          className="flex rounded-controle border border-pedra-300 p-0.5"
        >
          {(["texto", "blocos"] as const).map((opcao) => (
            <button
              key={opcao}
              type="button"
              aria-pressed={modo === opcao}
              className={`rounded-sm px-2.5 py-0.5 text-[0.8125rem] transition-colors duration-(--duracao-rapida) ${
                modo === opcao
                  ? "bg-pedra-900 text-superficie"
                  : "text-pedra-600 hover:bg-pedra-100"
              }`}
              onClick={() => setModo(opcao)}
            >
              {opcao === "texto" ? "Texto" : "Blocos"}
            </button>
          ))}
        </div>
      </div>
      {modo === "blocos" ? (
        <EditorDeBlocos
          valor={valor}
          aoMudar={aoMudar}
          funcoes={funcoes}
          constantes={constantes}
          campos={campos}
          erro={erro}
        />
      ) : (
        <>
          <div className="relative">
            {/* Espelho do texto, por trás: só desenha o erro, o par do cursor e o parêntese sem par. */}
            <pre
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words rounded-controle border border-transparent px-2 py-1.5 font-mono text-sm text-transparent"
            >
              <Espelho valor={valor} posicaoDoErro={erro?.posicao} par={par} semPar={semPar} />
            </pre>
            <textarea
              ref={campo}
              id={id}
              rows={3}
              spellCheck={false}
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={aberta}
              aria-controls={aberta ? idDaLista : undefined}
              aria-activedescendant={
                ativa === null || !aberta ? undefined : `${idDaLista}-${ativa}`
              }
              value={valor}
              aria-invalid={erro ? true : undefined}
              aria-describedby={erro ? idDoErro : undefined}
              className="relative w-full rounded-controle border border-pedra-300 bg-transparent px-2 py-1.5 font-mono text-sm aria-[invalid=true]:border-erro-300"
              onChange={(e) => {
                aoMudar(e.target.value);
                setCursor(e.target.selectionStart);
                setAtiva(null);
                setFechada(false);
              }}
              onKeyDown={aoTeclar}
              onSelect={(e) => setCursor(e.currentTarget.selectionStart)}
            />
          </div>

          {erro ? (
            <p id={idDoErro} role="alert" className="text-sm text-erro-700">
              {erro.mensagem}
            </p>
          ) : null}

          {aberta ? (
            <ul
              id={idDaLista}
              role="listbox"
              aria-label="Sugestões"
              className="overflow-hidden rounded-controle border border-pedra-200 bg-superficie text-sm shadow-elevada"
            >
              {sugestoes.map((sugestao, indice) => (
                <li
                  key={sugestao.nome}
                  id={`${idDaLista}-${indice}`}
                  role="option"
                  aria-selected={indice === ativa}
                  className={`cursor-pointer px-2.5 py-1.5 ${indice === ativa ? "bg-sinal-100" : "hover:bg-pedra-100"}`}
                  // `mousedown` e não `click`: o campo não pode perder o foco (e as sugestões) antes.
                  onMouseDown={(evento) => {
                    evento.preventDefault();
                    inserir(sugestao.inserir, true);
                  }}
                >
                  <span className="font-mono">{sugestao.nome}</span>{" "}
                  <span className="text-pedra-500">{sugestao.detalhe}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {chamada && funcaoDaDica ? (
            <DicaDaFuncao funcao={funcaoDaDica} argumento={chamada.argumento} />
          ) : null}

          <fieldset className="text-sm" role="group" aria-label="Funções disponíveis">
            <legend className="font-medium text-pedra-600">Funções disponíveis</legend>
            <ul className="mt-1 flex flex-col gap-1">
              {funcoes.map((funcao) => (
                <li key={funcao.nome} className="flex flex-wrap items-baseline gap-2">
                  <button
                    type="button"
                    aria-label={`Inserir ${funcao.assinatura}`}
                    className="rounded-controle bg-pedra-100 px-1.5 font-mono hover:bg-pedra-200"
                    onClick={() => inserir(`${funcao.nome}(`, false)}
                  >
                    {funcao.assinatura}
                  </button>
                  <span className="text-pedra-600">{funcao.descricao}</span>
                </li>
              ))}
            </ul>
          </fieldset>

          <fieldset className="text-sm" role="group" aria-label="Campos e constantes">
            <legend className="font-medium text-pedra-600">Campos e constantes</legend>
            <div className="mt-1 flex flex-wrap gap-1">
              {campos.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  title={c.rotulo}
                  className="rounded-controle bg-pedra-100 px-1.5 font-mono hover:bg-pedra-200"
                  onClick={() => inserir(c.id, false)}
                >
                  {c.id}
                </button>
              ))}
              {constantes.map((constante) => (
                <button
                  key={constante}
                  type="button"
                  className="rounded-controle bg-pedra-100 px-1.5 font-mono hover:bg-pedra-200"
                  onClick={() => inserir(constante, false)}
                >
                  {constante}
                </button>
              ))}
            </div>
          </fieldset>
        </>
      )}
    </div>
  );
}

/** A assinatura da função com o argumento atual em destaque, mais a descrição e o exemplo. */
function DicaDaFuncao({ funcao, argumento }: { funcao: FuncaoDoCatalogo; argumento: number }) {
  const argumentos = argumentosDaAssinatura(funcao.assinatura);
  const destaque = argumentoAtivo(argumentos, argumento);
  return (
    <div
      role="note"
      aria-label={`Ajuda da função ${funcao.nome}`}
      className="rounded-controle border border-pedra-200 bg-pedra-100 px-3 py-2 text-sm"
    >
      <p className="font-mono">
        {funcao.nome}(
        {argumentos.map((nome, indice) => (
          <span key={indice}>
            {indice > 0 ? ", " : ""}
            <span
              aria-current={indice === destaque ? "true" : undefined}
              className={indice === destaque ? "rounded-sm bg-sinal-100 font-semibold" : ""}
            >
              {nome}
            </span>
          </span>
        ))}
        )
      </p>
      <p className="mt-1 text-pedra-600">{funcao.descricao}</p>
      <p className="mt-0.5 text-pedra-500">
        Exemplo: <span className="font-mono">{funcao.exemplo}</span>
      </p>
    </div>
  );
}

type TipoDeMarca = "normal" | "erro" | "par" | "semPar";

/** O texto espelhado, com as marcas: o erro do servidor (por caracteres), os pares e os sem par. */
function Espelho({
  valor,
  posicaoDoErro,
  par,
  semPar,
}: {
  valor: string;
  posicaoDoErro: { inicio: number; fim: number } | null | undefined;
  par: [number, number] | null;
  semPar: number[];
}) {
  const caracteres = Array.from(valor);
  const tipos: TipoDeMarca[] = caracteres.map(() => "normal");

  // Os parênteses vêm em índices UTF-16 (os do `<textarea>`); o erro, em caracteres.
  const emCaracteres = new Map<number, number>();
  let unidades = 0;
  caracteres.forEach((c, i) => {
    emCaracteres.set(unidades, i);
    unidades += c.length;
  });
  for (const indice of par ?? []) {
    const i = emCaracteres.get(indice);
    if (i !== undefined) tipos[i] = "par";
  }
  for (const indice of semPar) {
    const i = emCaracteres.get(indice);
    if (i !== undefined) tipos[i] = "semPar";
  }
  if (
    posicaoDoErro &&
    posicaoDoErro.inicio >= 0 &&
    posicaoDoErro.fim > posicaoDoErro.inicio &&
    posicaoDoErro.fim <= caracteres.length
  ) {
    for (let i = posicaoDoErro.inicio; i < posicaoDoErro.fim; i++) tipos[i] = "erro";
  }

  const trechos: { tipo: TipoDeMarca; texto: string }[] = [];
  caracteres.forEach((c, i) => {
    const tipo = tipos[i] ?? "normal";
    const ultimo = trechos[trechos.length - 1];
    // Só o normal e o erro se agrupam; cada parêntese marcado é o seu próprio trecho.
    if (ultimo && ultimo.tipo === tipo && (tipo === "normal" || tipo === "erro")) ultimo.texto += c;
    else trechos.push({ tipo, texto: c });
  });

  return (
    <>
      {trechos.map((trecho, i) => {
        if (trecho.tipo === "erro") {
          return (
            <mark
              key={i}
              data-testid="trecho-com-erro"
              className="bg-erro-50 text-transparent underline decoration-erro-700 decoration-wavy"
            >
              {trecho.texto}
            </mark>
          );
        }
        if (trecho.tipo === "par") {
          return (
            <mark
              key={i}
              data-testid="par-do-cursor"
              className="rounded-sm bg-sinal-100 text-transparent"
            >
              {trecho.texto}
            </mark>
          );
        }
        if (trecho.tipo === "semPar") {
          return (
            <mark
              key={i}
              data-testid="parentese-sem-par"
              className="bg-aviso-50 text-transparent underline decoration-aviso-700 decoration-wavy"
            >
              {trecho.texto}
            </mark>
          );
        }
        return <span key={i}>{trecho.texto}</span>;
      })}
    </>
  );
}

interface Sugestao {
  nome: string;
  detalhe: string;
  inserir: string;
}

function sugerir(
  antesDoCursor: string,
  funcoes: FuncaoDoCatalogo[],
  constantes: string[],
  campos: { id: string; rotulo: string }[],
): Sugestao[] {
  const palavra = FIM_DA_PALAVRA.exec(antesDoCursor)?.[0]?.toLowerCase();
  if (!palavra) return [];
  const comeca = (texto: string) =>
    texto.toLowerCase().startsWith(palavra) && texto.toLowerCase() !== palavra;
  return [
    ...funcoes
      .filter((f) => comeca(f.nome))
      .map((f) => ({ nome: f.nome, detalhe: f.assinatura, inserir: `${f.nome}(` })),
    ...constantes.filter(comeca).map((c) => ({ nome: c, detalhe: "constante", inserir: c })),
    ...campos
      .filter((c) => comeca(c.id))
      .map((c) => ({ nome: c.id, detalhe: c.rotulo, inserir: c.id })),
  ];
}
