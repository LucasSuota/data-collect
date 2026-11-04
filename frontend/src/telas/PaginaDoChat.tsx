import { useEffect, useRef, useState } from "react";
import type { Conversa } from "../api/cliente";
import { useApi } from "../api/contexto";
import { mensagemDoErro } from "../lib/erros";
import { Aviso, Botao, Icone } from "../ui";
import { lerCitacoes, type Citacao } from "./citacoes";

interface Mensagem {
  papel: "pessoa" | "assistente";
  texto: string;
  citacoes: Citacao[];
  semIa?: boolean;
}

/**
 * O assistente sobre o app e sobre os dados da equipe (§2.5). Os números e as citações vêm do
 * servidor, conferidos por código; aqui só se mostra o que ele devolveu, com as fontes.
 */
export function PaginaDoChat() {
  const api = useApi();
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [conversas, setConversas] = useState<Conversa[]>([]);
  const [conversaId, setConversaId] = useState<number | null>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void api.listarConversas().then(setConversas, () => undefined);
  }, [api]);
  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: "end" });
  }, [mensagens]);

  async function abrir(id: number) {
    try {
      const c = await api.obterConversa(id);
      setConversaId(id);
      setMensagens(
        c.mensagens.map((m) => ({
          papel: m.papel,
          texto: m.texto,
          citacoes: lerCitacoes(m.citacoes),
        })),
      );
    } catch (e) {
      setErro(mensagemDoErro(e));
    }
  }

  async function apagar(id: number) {
    await api.apagarConversa(id);
    setConversas((atual) => atual.filter((c) => c.id !== id));
    if (conversaId === id) novaConversa();
  }

  function novaConversa() {
    setConversaId(null);
    setMensagens([]);
  }

  async function enviar() {
    const pergunta = texto.trim();
    if (!pergunta || enviando) return;
    setTexto("");
    setErro(null);
    setEnviando(true);
    setMensagens((m) => [
      ...m,
      { papel: "pessoa", texto: pergunta, citacoes: [] },
      { papel: "assistente", texto: "", citacoes: [] },
    ]);
    try {
      await api.conversar({ mensagem: pergunta, conversa_id: conversaId }, (evento) => {
        if (evento.tipo === "conversa") setConversaId(evento.conversa_id);
        if (evento.tipo === "texto") {
          setMensagens((m) =>
            m.map((x, i) => (i === m.length - 1 ? { ...x, texto: x.texto + evento.texto } : x)),
          );
        }
        if (evento.tipo === "fim") {
          setMensagens((m) =>
            m.map((x, i) =>
              i === m.length - 1
                ? { ...x, citacoes: lerCitacoes(evento.citacoes), semIa: !evento.usou_ia }
                : x,
            ),
          );
        }
      });
      void api.listarConversas().then(setConversas, () => undefined);
    } catch (e) {
      setErro(mensagemDoErro(e));
      setMensagens((m) => m.slice(0, -1));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
      <aside aria-label="Conversas" className="flex flex-col gap-2">
        <Botao onClick={novaConversa}>
          <Icone nome="mais" /> Nova conversa
        </Botao>
        <ul className="flex flex-col gap-1">
          {conversas.map((c) => (
            <li key={c.id} className="flex items-center gap-1">
              <button
                type="button"
                aria-current={c.id === conversaId}
                onClick={() => void abrir(c.id)}
                className={`min-h-11 flex-1 truncate rounded-controle px-3 text-left text-sm ${c.id === conversaId ? "bg-sinal-100 font-semibold text-sinal-600" : "hover:bg-pedra-100"}`}
              >
                {c.titulo}
              </button>
              <button
                type="button"
                aria-label={`Apagar a conversa “${c.titulo}”`}
                onClick={() => void apagar(c.id)}
                className="grid size-11 place-items-center rounded-controle text-pedra-500 hover:bg-erro-50 hover:text-erro-700"
              >
                <Icone nome="lixeira" />
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-h-[60dvh] flex-col gap-3">
        <h1 className="text-3xl font-extrabold">Assistente</h1>
        <div className="flex flex-1 flex-col gap-3" aria-live="polite">
          {mensagens.length === 0 ? (
            <p className="rounded-cartao border border-dashed border-pedra-300 p-5 text-sm text-pedra-600">
              Pergunte como usar o app (“como crio um vínculo entre formulários?”) ou sobre os
              registros (“quantos corpos de prova foram não conformes em outubro?”). Os números vêm
              de consultas do servidor, nunca da IA.
            </p>
          ) : null}
          {mensagens.map((m, i) => (
            <div
              key={i}
              className={`max-w-[85%] rounded-cartao px-4 py-3 text-sm ${m.papel === "pessoa" ? "self-end bg-sinal-500 text-superficie" : "self-start border border-pedra-200 bg-superficie"}`}
            >
              <p className="whitespace-pre-wrap">
                {m.texto || (enviando && i === mensagens.length - 1 ? "…" : "")}
              </p>
              {m.semIa ? (
                <p className="mt-2 text-xs text-pedra-600">
                  Sem IA configurada: só os trechos e resultados encontrados.
                </p>
              ) : null}
              {m.citacoes.length > 0 ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {m.citacoes.map((c, j) => (
                    <li key={j}>
                      {c.href ? (
                        <a
                          href={c.href}
                          className="inline-flex min-h-9 items-center rounded-controle bg-sinal-100 px-2 text-xs font-medium text-sinal-600"
                        >
                          {c.rotulo}
                        </a>
                      ) : (
                        <span className="rounded-controle bg-pedra-100 px-2 py-1 text-xs">
                          {c.rotulo}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
          <div ref={fim} />
        </div>
        {erro ? <Aviso tom="erro">{erro}</Aviso> : null}
        <form
          className="sticky bottom-20 flex gap-2 sm:bottom-4"
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          <label className="flex-1">
            <span className="sr-only">Sua pergunta</span>
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Pergunte ao assistente"
              maxLength={2000}
              className="min-h-11 w-full rounded-controle border border-pedra-300 bg-superficie px-3 text-sm"
            />
          </label>
          <Botao type="submit" variante="primario" carregando={enviando} disabled={!texto.trim()}>
            Enviar
          </Botao>
        </form>
      </section>
    </div>
  );
}
