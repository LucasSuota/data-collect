import { useId, useState } from "react";
import type { Esquemas } from "../api/cliente";

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
 * Edita a fórmula com ajuda: funções e campos do catálogo, autocompletar e o trecho do erro
 * sublinhado. Nenhum parse de fórmula aqui: o servidor valida e diz onde está o erro.
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
  const [cursor, setCursor] = useState(valor.length);

  const caracteres = Array.from(valor);
  const trecho = trechoComErro(caracteres, erro?.posicao);
  const sugestoes = sugerir(caracteres.slice(0, cursor).join(""), funcoes, constantes, campos);

  function inserir(texto: string, substituindoAPalavra: boolean) {
    const antes = valor.slice(0, cursor);
    const base = substituindoAPalavra ? antes.replace(FIM_DA_PALAVRA, "") : antes;
    const novo = base + texto + valor.slice(cursor);
    aoMudar(novo);
    setCursor((base + texto).length);
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {rotulo}
      </label>
      <div className="relative">
        {/* Espelho do texto, por trás: só serve para desenhar o sublinhado do trecho com erro. */}
        <pre
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words rounded border border-transparent px-2 py-1.5 font-mono text-sm text-transparent"
        >
          {trecho ? (
            <>
              {trecho.antes}
              <mark
                data-testid="trecho-com-erro"
                className="bg-red-100 text-transparent underline decoration-red-600 decoration-wavy"
              >
                {trecho.erro}
              </mark>
              {trecho.depois}
            </>
          ) : (
            valor
          )}
        </pre>
        <textarea
          id={id}
          rows={3}
          spellCheck={false}
          value={valor}
          aria-invalid={erro ? true : undefined}
          aria-describedby={erro ? idDoErro : undefined}
          className="relative w-full rounded border border-slate-300 bg-transparent px-2 py-1.5 font-mono text-sm aria-[invalid=true]:border-red-500"
          onChange={(e) => {
            aoMudar(e.target.value);
            setCursor(e.target.selectionStart);
          }}
          onSelect={(e) => setCursor(e.currentTarget.selectionStart)}
        />
      </div>

      {erro ? (
        <p id={idDoErro} role="alert" className="text-sm text-red-700">
          {erro.mensagem}
        </p>
      ) : null}

      {sugestoes.length > 0 ? (
        <ul
          role="listbox"
          aria-label="Sugestões"
          className="rounded border border-slate-200 bg-white text-sm shadow"
        >
          {sugestoes.map((sugestao) => (
            <li
              key={sugestao.nome}
              role="option"
              aria-selected={false}
              tabIndex={0}
              className="cursor-pointer px-2 py-1 hover:bg-slate-100 focus:bg-slate-100"
              onClick={() => inserir(sugestao.inserir, true)}
              onKeyDown={(evento) => {
                if (evento.key === "Enter" || evento.key === " ") {
                  evento.preventDefault();
                  inserir(sugestao.inserir, true);
                }
              }}
            >
              <span className="font-mono">{sugestao.nome}</span>{" "}
              <span className="text-slate-500">{sugestao.detalhe}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <fieldset className="text-sm" role="group" aria-label="Funções disponíveis">
        <legend className="font-medium text-slate-600">Funções disponíveis</legend>
        <ul className="mt-1 flex flex-col gap-1">
          {funcoes.map((funcao) => (
            <li key={funcao.nome} className="flex flex-wrap items-baseline gap-2">
              <button
                type="button"
                aria-label={`Inserir ${funcao.assinatura.replace(/\(.*$/, "")}(n)`.replace(
                  "(n)",
                  funcao.assinatura.slice(funcao.nome.length),
                )}
                className="rounded bg-slate-100 px-1.5 font-mono"
                onClick={() => inserir(`${funcao.nome}(`, false)}
              >
                {funcao.assinatura}
              </button>
              <span className="text-slate-600">{funcao.descricao}</span>
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset className="text-sm" role="group" aria-label="Campos e constantes">
        <legend className="font-medium text-slate-600">Campos e constantes</legend>
        <div className="mt-1 flex flex-wrap gap-1">
          {campos.map((campo) => (
            <button
              key={campo.id}
              type="button"
              title={campo.rotulo}
              className="rounded bg-slate-100 px-1.5 font-mono"
              onClick={() => inserir(campo.id, false)}
            >
              {campo.id}
            </button>
          ))}
          {constantes.map((constante) => (
            <button
              key={constante}
              type="button"
              className="rounded bg-slate-100 px-1.5 font-mono"
              onClick={() => inserir(constante, false)}
            >
              {constante}
            </button>
          ))}
        </div>
      </fieldset>
    </div>
  );
}

/** Divide o texto em antes / trecho com erro / depois, por caracteres; fora do texto, nada. */
function trechoComErro(
  caracteres: string[],
  posicao: { inicio: number; fim: number } | null | undefined,
): { antes: string; erro: string; depois: string } | null {
  if (!posicao || posicao.inicio < 0 || posicao.fim <= posicao.inicio) return null;
  if (posicao.fim > caracteres.length) return null;
  return {
    antes: caracteres.slice(0, posicao.inicio).join(""),
    erro: caracteres.slice(posicao.inicio, posicao.fim).join(""),
    depois: caracteres.slice(posicao.fim).join(""),
  };
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
