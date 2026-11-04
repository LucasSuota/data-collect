import { useCallback, useEffect, useState } from "react";
import type { ConfigDaIa, UsoDaIa } from "../api/cliente";
import { useApi } from "../api/contexto";
import { mensagemDoErro } from "../lib/erros";
import { Aviso, Botao, CampoDeTexto, Esqueleto, Interruptor, Selecao } from "../ui";

type Provedor = ConfigDaIa["provedor"];

const NOMES_DOS_PROVEDORES: Record<Provedor, string> = {
  anthropic: "Anthropic (Claude)",
  openai_compativel:
    "API compatível com OpenAI (OpenAI, Azure, Ollama, LM Studio, vLLM, OpenRouter, Groq, Gemini…)",
};

/** Configuração da IA por equipe (AGENTS.md §2.5, §2.15): desligada por padrão, com aviso e aceite. */
export function PaginaDaIa() {
  const api = useApi();
  const [config, setConfig] = useState<ConfigDaIa | null>(null);
  const [uso, setUso] = useState<UsoDaIa | null>(null);
  const [ativa, setAtiva] = useState(false);
  const [provedor, setProvedor] = useState<Provedor>("anthropic");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelo, setModelo] = useState("");
  const [embeddings, setEmbeddings] = useState("");
  const [chave, setChave] = useState("");
  const [aceite, setAceite] = useState(false);
  const [mensagem, setMensagem] = useState<{ tom: "erro" | "sucesso"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const aplicar = useCallback((c: ConfigDaIa) => {
    setConfig(c);
    setAtiva(c.ativa);
    setProvedor(c.provedor);
    setBaseUrl(c.base_url ?? "");
    setModelo(c.modelo ?? "");
    setEmbeddings(c.modelo_embeddings ?? "");
    setChave("");
  }, []);

  useEffect(() => {
    void api
      .configDaIa()
      .then(aplicar, (e) => setMensagem({ tom: "erro", texto: mensagemDoErro(e) }));
    void api.usoDaIa().then(setUso, () => undefined);
  }, [api, aplicar]);

  async function executar(acao: () => Promise<string>) {
    setOcupado(true);
    setMensagem(null);
    try {
      setMensagem({ tom: "sucesso", texto: await acao() });
    } catch (e) {
      setMensagem({ tom: "erro", texto: mensagemDoErro(e) });
    } finally {
      setOcupado(false);
    }
  }

  const ligandoAgora = ativa && !config?.ativa;
  const nomeDoProvedor =
    provedor === "anthropic" ? "a Anthropic" : baseUrl || "o provedor configurado";

  if (config === null) {
    return (
      <div role="status" aria-label="Carregando" className="flex flex-col gap-3">
        <Esqueleto className="h-9 w-72" />
        <Esqueleto className="h-80 max-w-xl rounded-cartao" />
      </div>
    );
  }

  return (
    <div className="flex max-w-xl flex-col gap-5">
      <header>
        <h1 className="text-3xl font-extrabold">Inteligência artificial</h1>
        <p className="mt-1 text-sm text-pedra-600">
          A IA nunca calcula: só busca e redige. Os cálculos e as conferências são do servidor.
        </p>
      </header>
      {mensagem ? <Aviso tom={mensagem.tom}>{mensagem.texto}</Aviso> : null}

      <form
        className="flex flex-col gap-4 rounded-cartao border border-pedra-200 bg-superficie p-4 shadow-cartao"
        onSubmit={(e) => {
          e.preventDefault();
          void executar(async () => {
            aplicar(
              await api.salvarConfigDaIa({
                ativa,
                aceite_do_aviso: aceite,
                provedor,
                base_url: baseUrl.trim() || null,
                modelo: modelo.trim() || null,
                modelo_embeddings: embeddings.trim() || null,
                chave: chave.trim() || null,
              }),
            );
            return "Configuração salva.";
          });
        }}
      >
        <Interruptor
          rotulo="Ativar a IA nesta equipe"
          descricao="Desligada por padrão."
          ligado={ativa}
          aoMudar={setAtiva}
        />
        <Selecao
          rotulo="Provedor"
          tamanho="normal"
          value={provedor}
          onChange={(e) => setProvedor(e.target.value as Provedor)}
        >
          {(Object.keys(NOMES_DOS_PROVEDORES) as Provedor[]).map((p) => (
            <option key={p} value={p}>
              {NOMES_DOS_PROVEDORES[p]}
            </option>
          ))}
        </Selecao>
        {provedor === "openai_compativel" ? (
          <CampoDeTexto
            rotulo="Endereço da API (base_url)"
            type="url"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1"
          />
        ) : null}
        <CampoDeTexto rotulo="Modelo" value={modelo} onChange={(e) => setModelo(e.target.value)} />
        <CampoDeTexto
          rotulo="Modelo de embeddings (opcional)"
          value={embeddings}
          onChange={(e) => setEmbeddings(e.target.value)}
          dica="Habilita a busca semântica. Sem ele, vale só filtro e BM25."
        />
        <CampoDeTexto
          rotulo="Chave de API"
          type="password"
          autoComplete="off"
          value={chave}
          onChange={(e) => setChave(e.target.value)}
          dica={
            config.chave_definida
              ? "Já há uma chave guardada (cifrada). Deixe em branco para manter; ela nunca é mostrada."
              : "Guardada cifrada no servidor e nunca devolvida pela API."
          }
        />
        {ligandoAgora ? (
          <label className="flex min-h-11 items-start gap-3 rounded-controle border border-aviso-300 bg-aviso-50 p-3 text-sm">
            <input
              type="checkbox"
              checked={aceite}
              onChange={(e) => setAceite(e.target.checked)}
              className="mt-0.5 size-5 accent-sinal-500"
            />
            <span>
              Entendo que, com a IA ativa, trechos dos formulários e dos registros desta equipe
              serão enviados a <strong>{nomeDoProvedor}</strong>. Campos marcados com “ia: false”
              nunca são enviados.
            </span>
          </label>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Botao
            type="submit"
            variante="primario"
            carregando={ocupado}
            disabled={ligandoAgora && !aceite}
          >
            Salvar
          </Botao>
          <Botao
            disabled={ocupado}
            onClick={() => void executar(async () => (await api.testarIa()).mensagem)}
          >
            Testar conexão
          </Botao>
          <Botao
            disabled={ocupado || !config.ativa}
            onClick={() =>
              void executar(async () => {
                const r = await api.reindexarIa();
                return `Índice atualizado: ${r.gravados} gravados, ${r.removidos} removidos, ${r.iguais} sem mudança.`;
              })
            }
          >
            Reindexar dados
          </Botao>
        </div>
        {config.consentimento_em ? (
          <p className="text-xs text-pedra-500">
            Aviso aceito em {new Date(config.consentimento_em).toLocaleDateString("pt-BR")}.
          </p>
        ) : null}
      </form>

      {uso ? (
        <section
          aria-labelledby="uso"
          className="rounded-cartao border border-pedra-200 bg-superficie p-4"
        >
          <h2 id="uso" className="font-bold">
            Uso
          </h2>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
            <dt className="text-pedra-600">Suas chamadas</dt>
            <dd className="font-mono">
              {uso.chamadas_da_pessoa} / {uso.limite_de_chamadas_por_pessoa}
            </dd>
            <dt className="text-pedra-600">Chamadas da equipe</dt>
            <dd className="font-mono">
              {uso.chamadas_da_equipe} / {uso.limite_de_chamadas_por_equipe}
            </dd>
            <dt className="text-pedra-600">Tokens da equipe</dt>
            <dd className="font-mono">
              {uso.tokens_da_equipe} / {uso.limite_de_tokens_por_equipe}
            </dd>
          </dl>
        </section>
      ) : null}
    </div>
  );
}
