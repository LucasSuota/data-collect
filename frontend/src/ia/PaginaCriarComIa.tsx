import { useState } from "react";
import { useApi } from "../api/contexto";
import { ErroDaApi } from "../api/cliente";
import { Construtor } from "../construtor/Construtor";
import { Falha, mensagemDe } from "../paginas/Estado";
import type { Rota } from "../rotas";
import { atribuirErrosDoLote, deGerados, type Rascunho } from "./rascunhos";

/** Espelha o `maxLength` do pedido no OpenAPI: o servidor recusa texto maior (422). */
const PEDIDO_MAXIMO = 4000;

let proximaChave = 0;
const gerarChave = () => `rascunho-${++proximaChave}`;

interface Props {
  navegar: (rota: Rota) => void;
}

/**
 * "Criar com IA": a pessoa descreve o que quer, a IA propõe formulários, e ela revisa, ajusta e
 * aprova tudo de uma vez (AGENTS.md §2.5). Nada é salvo antes de "Publicar todos". A IA só redige
 * a definição; quem valida, em cada rodada, é o servidor.
 */
export function PaginaCriarComIa({ navegar }: Props) {
  const cliente = useApi();
  const [pedido, setPedido] = useState("");
  const [rascunhos, setRascunhos] = useState<Rascunho[]>([]);
  const [editando, setEditando] = useState<string | null>(null);
  const [gerando, setGerando] = useState(false);
  const [publicando, setPublicando] = useState(false);
  const [falha, setFalha] = useState<string | null>(null);
  const [globais, setGlobais] = useState<string[]>([]);

  const emEdicao = rascunhos.find((r) => r.chave === editando);
  if (emEdicao) {
    return (
      <Construtor
        modo={{
          tipo: "rascunho",
          rascunho: emEdicao,
          nomesDosIrmaos: rascunhos.filter((r) => r.chave !== emEdicao.chave).map((r) => r.nome),
          aoConcluir: (nome, definicao) => {
            // Os erros antigos valiam para a definição anterior: a próxima rodada os recalcula.
            setRascunhos((atuais) =>
              atuais.map((r) =>
                r.chave === emEdicao.chave ? { ...r, nome, definicao, erros: [] } : r,
              ),
            );
            setEditando(null);
          },
          aoCancelar: () => setEditando(null),
        }}
        navegar={navegar}
      />
    );
  }

  async function gerar() {
    setGerando(true);
    setFalha(null);
    setGlobais([]);
    try {
      const proposta = await cliente.gerarFormularios({
        pedido,
        rascunhos: rascunhos.map(({ nome, definicao }) => ({ nome, definicao })),
      });
      setRascunhos(deGerados(proposta.formularios, gerarChave));
    } catch (erro) {
      setFalha(mensagemDe(erro));
    } finally {
      setGerando(false);
    }
  }

  async function publicarTodos() {
    setPublicando(true);
    setFalha(null);
    setGlobais([]);
    try {
      await cliente.criarFormulariosEmLote(
        rascunhos.map(({ nome, definicao }) => ({ nome, definicao })),
      );
      navegar({ nome: "formularios" });
    } catch (erro) {
      if (erro instanceof ErroDaApi && erro.status === 422) {
        // Nada foi criado: o servidor valida o conjunto inteiro e devolve os erros por formulário.
        const atribuido = atribuirErrosDoLote(rascunhos, erro.erros);
        setRascunhos(atribuido.rascunhos);
        setGlobais(atribuido.globais);
      }
      setFalha(mensagemDe(erro));
    } finally {
      setPublicando(false);
    }
  }

  const totalDeErros = rascunhos.reduce((soma, r) => soma + r.erros.length, 0);

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Criar formulários com IA</h1>
        <a href="#/construtor" className="text-sm underline">
          Usar o construtor manual
        </a>
      </div>
      <p className="text-sm text-slate-600">
        Descreva o que quer coletar. A IA só escreve a definição dos formulários; o sistema continua
        sendo quem valida e calcula, e nada é salvo até você publicar.
      </p>

      <div className="flex flex-col gap-1">
        <label htmlFor="pedido-ia" className="text-sm font-medium">
          O que você quer criar?
        </label>
        <textarea
          id="pedido-ia"
          rows={4}
          maxLength={PEDIDO_MAXIMO}
          className="rounded border border-slate-300 px-2 py-1.5"
          value={pedido}
          aria-describedby="contador-do-pedido"
          onChange={(e) => setPedido(e.target.value)}
        />
        <span id="contador-do-pedido" className="text-xs text-slate-500">
          {pedido.length}/{PEDIDO_MAXIMO}
        </span>
      </div>
      <div>
        <button
          type="button"
          disabled={gerando || pedido.trim() === ""}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
          onClick={() => void gerar()}
        >
          {gerando ? "Gerando…" : rascunhos.length > 0 ? "Refinar rascunhos" : "Gerar formulários"}
        </button>
      </div>

      {falha ? <Falha mensagem={falha} /> : null}
      {globais.length > 0 ? <Falha mensagem={globais.join(" · ")} /> : null}

      {rascunhos.length > 0 ? (
        <section aria-label="Rascunhos" className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Rascunhos</h2>
          {totalDeErros > 0 ? (
            <p className="text-sm text-slate-600">
              Corrija os erros no construtor antes de publicar: se algum rascunho for inválido, o
              servidor recusa o conjunto inteiro e nada é criado.
            </p>
          ) : null}
          <ul className="flex flex-col gap-2">
            {rascunhos.map((rascunho, indice) => (
              <li
                key={rascunho.chave}
                className={`flex flex-col gap-2 rounded border p-3 ${
                  rascunho.erros.length > 0 ? "border-red-400" : "border-slate-200"
                }`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    aria-label={`Nome do rascunho ${indice + 1}`}
                    className="min-w-48 flex-1 rounded border border-slate-300 px-2 py-1.5"
                    value={rascunho.nome}
                    onChange={(e) =>
                      setRascunhos((atuais) =>
                        atuais.map((r) =>
                          r.chave === rascunho.chave ? { ...r, nome: e.target.value } : r,
                        ),
                      )
                    }
                  />
                  <span
                    className={`text-sm ${rascunho.erros.length > 0 ? "text-red-700" : "text-green-700"}`}
                  >
                    {rascunho.erros.length > 0 ? `${rascunho.erros.length} erro(s)` : "Sem erros"}
                  </span>
                  <button
                    type="button"
                    className="rounded border border-slate-300 px-2 py-1 text-sm"
                    aria-label={`Editar o rascunho ${rascunho.nome}`}
                    onClick={() => setEditando(rascunho.chave)}
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    className="rounded border border-red-300 px-2 py-1 text-sm text-red-700"
                    aria-label={`Remover o rascunho ${rascunho.nome}`}
                    onClick={() =>
                      setRascunhos((atuais) => atuais.filter((r) => r.chave !== rascunho.chave))
                    }
                  >
                    Remover
                  </button>
                </div>
                {rascunho.erros.length > 0 ? (
                  <ul className="list-disc pl-5 text-sm text-red-700">
                    {rascunho.erros.map((erro, posicao) => (
                      <li key={posicao}>{`${erro.campo}: ${erro.mensagem}`}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
          <div>
            <button
              type="button"
              disabled={publicando}
              className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-60"
              onClick={() => void publicarTodos()}
            >
              {publicando ? "Publicando…" : "Publicar todos"}
            </button>
          </div>
        </section>
      ) : null}
    </section>
  );
}
