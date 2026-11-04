import { useContext, useMemo, useState } from "react";
import { ErroDaApi } from "../api/cliente";
import { useApi } from "../api/contexto";
import { ContextoDaSessao } from "../auth/sessao";
import type { Rota } from "../rotas";
import { Aviso, EstadoVazio } from "../ui";
import { Falha, useCarga } from "../paginas/Estado";
import { Arestas } from "./Arestas";
import { carregarMapa, type DadosDoMapa } from "./carregarMapa";
import { detalheDoNo } from "./detalhe";
import { cadeiaDe, montarGrafoDeFormularios, montarGrafoDeRegistros } from "./grafo";
import { Inspetor } from "./Inspetor";
import { ListaDoMapa } from "./ListaDoMapa";
import { organizar } from "./layout";
import { MEDIDAS_DO_MAPA, alturaDoNo } from "./medidas";
import { NoDoMapa } from "./NoDoMapa";
import { Quadro } from "./Quadro";
import { adicionarReferencia } from "./vinculo";

type Nivel = "estrutura" | "dados";

interface Props {
  navegar: (rota: Rota) => void;
}

/** O mapa de dependências: o que depende de quê, entre formulários e entre registros. */
export function PaginaDoMapa({ navegar }: Props) {
  const cliente = useApi();
  const [versao, setVersao] = useState(0);
  const carga = useCarga(() => carregarMapa(cliente), [cliente, versao]);

  return (
    <section className="flex flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Mapa de dependências</h1>
        <p className="mt-0.5 text-sm text-pedra-600">
          Cada seta leva valores da origem para quem depende dela. Arraste o fundo para mover; Ctrl
          ou ⌘ com a roda dá zoom.
        </p>
      </header>
      {carga.situacao === "carregando" ? (
        <p role="status" className="text-sm text-pedra-600">
          Carregando o mapa…
        </p>
      ) : null}
      {carga.situacao === "erro" ? <Falha mensagem={carga.mensagem} /> : null}
      {carga.situacao === "pronto" ? (
        <Mapa dados={carga.dados} navegar={navegar} aoVincular={() => setVersao((v) => v + 1)} />
      ) : null}
    </section>
  );
}

function Mapa({
  dados,
  navegar,
  aoVincular,
}: {
  dados: DadosDoMapa;
  navegar: Props["navegar"];
  aoVincular: () => void;
}) {
  const cliente = useApi();
  // Sem sessão (componente isolado, nos testes) tudo fica liberado; o servidor é quem barra.
  const sessao = useContext(ContextoDaSessao);
  const podeVincular = sessao?.pode("formularios:publicar") ?? true;
  const [origemId, setOrigemId] = useState<string | null>(null);
  const [resultado, setResultado] = useState<{
    tom: "sucesso" | "erro";
    texto: string;
    formularioId?: number;
  } | null>(null);

  const [nivel, setNivel] = useState<Nivel>("estrutura");
  const [incluirIsolados, setIncluirIsolados] = useState(false);
  // A seleção vale para o nível em que foi feita: trocar de nível a desfaz sem precisar de efeito.
  const [selecao, setSelecao] = useState<{ nivel: Nivel; id: string } | null>(null);
  const selecionadoId = selecao?.nivel === nivel ? selecao.id : null;

  const grafo = useMemo(
    () =>
      nivel === "estrutura"
        ? montarGrafoDeFormularios(dados.formularios, { incluirIsolados })
        : montarGrafoDeRegistros(dados.formularios, dados.registros, { incluirIsolados }),
    [dados, nivel, incluirIsolados],
  );
  const organizacao = useMemo(() => organizar(grafo, MEDIDAS_DO_MAPA), [grafo]);
  const alturas = useMemo(() => new Map(grafo.nos.map((no) => [no.id, alturaDoNo(no)])), [grafo]);
  const cadeia = selecionadoId === null ? null : cadeiaDe(grafo, selecionadoId);
  const detalhe = selecionadoId === null ? null : detalheDoNo(dados, selecionadoId);
  const selecionar = (id: string) => setSelecao({ nivel, id });

  /** Origem na porta da direita, dependente na da esquerda: o campo vai para o RASCUNHO do dependente. */
  async function vincular(dependenteNoId: string) {
    const origem = grafo.nos.find((n) => n.id === origemId);
    const dependente = grafo.nos.find((n) => n.id === dependenteNoId);
    setOrigemId(null);
    if (!origem || !dependente || origem.id === dependente.id) return;
    const nomeDaOrigem = dados.formularios.find((f) => f.id === origem.formularioId)?.nome;
    const formularioDependente = dados.formularios.find((f) => f.id === dependente.formularioId);
    if (!nomeDaOrigem || !formularioDependente) return;
    try {
      let rascunho = null;
      try {
        rascunho = await cliente.obterRascunho(formularioDependente.id);
      } catch (erro) {
        if (!(erro instanceof ErroDaApi && erro.status === 404)) throw erro;
      }
      const { definicao, jaExistia } = adicionarReferencia(
        rascunho?.definicao ?? formularioDependente.definicao,
        nomeDaOrigem,
      );
      if (jaExistia) {
        setResultado({
          tom: "erro",
          texto: `${formularioDependente.nome} já aponta para ${nomeDaOrigem}.`,
        });
        return;
      }
      await cliente.salvarRascunho(formularioDependente.id, definicao, rascunho?.revisao);
      setResultado({
        tom: "sucesso",
        texto: `Vínculo criado no rascunho da próxima versão de ${formularioDependente.nome}. Publique no construtor para valer.`,
        formularioId: formularioDependente.id,
      });
      aoVincular();
    } catch (erro) {
      setResultado({
        tom: "erro",
        texto: erro instanceof ErroDaApi ? erro.message : "Não foi possível criar o vínculo.",
      });
    }
  }
  const vinculavel = nivel === "estrutura" && podeVincular;

  if (dados.formularios.length === 0) {
    return (
      <EstadoVazio icone="mapa" titulo="Nada para mapear ainda">
        Crie formulários e ligue-os com campos do tipo Referência para ver as dependências aqui.
      </EstadoVazio>
    );
  }

  const semVinculos = grafo.arestas.length === 0;
  return (
    <>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div
          role="group"
          aria-label="Nível do mapa"
          className="flex rounded-controle border border-pedra-300 bg-superficie p-0.5"
        >
          {(
            [
              ["estrutura", "Formulários"],
              ["dados", "Registros e valores"],
            ] as const
          ).map(([valor, rotulo]) => (
            <button
              key={valor}
              type="button"
              aria-pressed={nivel === valor}
              onClick={() => setNivel(valor)}
              className={`min-h-8 rounded-controle px-3 text-sm font-medium transition-colors duration-(--duracao-rapida) ${nivel === valor ? "bg-pedra-900 text-superficie" : "text-pedra-700 hover:bg-pedra-100"}`}
            >
              {rotulo}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-pedra-700">
          <input
            type="checkbox"
            checked={incluirIsolados}
            onChange={(evento) => setIncluirIsolados(evento.target.checked)}
            className="size-4 accent-pedra-900"
          />
          Incluir sem vínculo
        </label>
      </div>

      {vinculavel ? (
        <Aviso tom="info">
          {origemId
            ? "Agora clique no ponto esquerdo do formulário dependente."
            : "Clique no ponto direito de um formulário e depois no ponto esquerdo de outro para criar o vínculo."}{" "}
          O servidor continua rejeitando ciclos ao publicar; versões publicadas nunca mudam.
        </Aviso>
      ) : null}
      {nivel === "estrutura" && !podeVincular ? (
        <p className="rounded-controle border border-dashed border-pedra-400 px-3 py-2 text-sm text-pedra-600">
          Criar vínculos pelo mapa requer a permissão “Criar e publicar versões”.
        </p>
      ) : null}
      {resultado ? (
        <Aviso
          tom={resultado.tom}
          acoes={
            resultado.formularioId !== undefined ? (
              <a
                href={`#/formularios/${resultado.formularioId}/editar`}
                className="min-h-11 px-2 py-2 text-sm font-semibold underline"
              >
                Abrir no construtor
              </a>
            ) : undefined
          }
        >
          {resultado.texto}
        </Aviso>
      ) : null}
      {dados.truncados.length > 0 ? (
        <Aviso tom="info">
          Mostrando só os registros mais recentes de {dados.truncados.join(", ")}: há mais do que o
          mapa carrega por versão.
        </Aviso>
      ) : null}
      {semVinculos ? (
        <Aviso tom="info">
          {nivel === "estrutura"
            ? "Nenhum formulário aponta para outro ainda. Adicione um campo do tipo Referência no construtor para criar uma dependência."
            : "Nenhum registro aponta para outro ainda. Preencha o campo de referência de um registro para ver a ligação."}
        </Aviso>
      ) : null}

      <div className="sm:hidden">
        <ListaDoMapa grafo={grafo} aoAbrir={(no) => selecionar(no.id)} />
      </div>
      <div className="relative hidden sm:block">
        <Quadro
          rotulo={`Mapa de ${nivel === "estrutura" ? "formulários" : "registros"}`}
          chave={`${nivel}-${incluirIsolados}-${grafo.nos.length}`}
          conteudo={{ largura: organizacao.largura, altura: organizacao.altura }}
        >
          <Arestas
            arestas={grafo.arestas}
            posicoes={organizacao.posicoes}
            alturas={alturas}
            largura={organizacao.largura}
            altura={organizacao.altura}
            realce={cadeia?.arestas ?? null}
          />
          {grafo.nos.map((no) => {
            const posicao = organizacao.posicoes.get(no.id);
            if (!posicao) return null;
            return (
              <NoDoMapa
                key={no.id}
                no={no}
                x={posicao.x}
                y={posicao.y}
                selecionado={no.id === selecionadoId}
                esmaecido={cadeia !== null && !cadeia.nos.has(no.id)}
                aoSelecionar={() => selecionar(no.id)}
                vinculo={
                  vinculavel
                    ? {
                        origemAtiva: origemId === no.id,
                        esperandoDependente: origemId !== null,
                        aoClicarNaDireita: () =>
                          setOrigemId((atual) => (atual === no.id ? null : no.id)),
                        aoClicarNaEsquerda: () => void vincular(no.id),
                      }
                    : undefined
                }
              />
            );
          })}
        </Quadro>
        {detalhe ? (
          <div className="absolute inset-y-3 right-3 z-10 flex w-80 max-w-[calc(100%-1.5rem)] flex-col">
            <Inspetor
              detalhe={detalhe}
              aoFechar={() => setSelecao(null)}
              aoSelecionar={selecionar}
              navegar={navegar}
            />
          </div>
        ) : (
          <p className="pointer-events-none absolute top-3 right-3 rounded-controle border border-pedra-200 bg-superficie/90 px-2.5 py-1.5 text-xs text-pedra-600">
            Clique num cartão para ver origem, dependentes e valores.
          </p>
        )}
      </div>
    </>
  );
}
