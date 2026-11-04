import { useState } from "react";
import { ErroDaApi } from "../api/cliente";
import { ComPermissao } from "../shell/permissoes";
import { useApi } from "../api/contexto";
import type { Contagens, Esquemas, ParametrosDeConsulta, ResumoDaIa } from "../api/cliente";
import { baixarArquivo, formatarCelula } from "../lib/formatacao";
import type { Rota } from "../rotas";
import { Botao, Cartao, EstadoVazio, Icone, SeloDeEstado } from "../ui";
import { CLASSE_DO_CONTROLE } from "../components/FormRenderer/Campo";
import { EsqueletoDaTabela } from "./esqueletos";
import { Falha, mensagemDe, useCarga } from "./Estado";

type Coluna = Esquemas["ColunaSaida"];

const POR_PAGINA = 25;

interface Props {
  formularioId: number;
  navegar: (rota: Rota) => void;
}

/** Os registros de uma versão, com colunas da definição, filtros, paginação e exportação CSV. */
export function PaginaDeRegistros({ formularioId, navegar }: Props) {
  const cliente = useApi();
  const [versaoId, setVersaoId] = useState<number | undefined>(undefined);
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [criadoDe, setCriadoDe] = useState("");
  const [criadoAte, setCriadoAte] = useState("");
  const [pagina, setPagina] = useState(0);
  const [falhaDoCsv, setFalhaDoCsv] = useState<string | null>(null);
  const [soMeus, setSoMeus] = useState(false);
  const [resumo, setResumo] = useState<ResumoDaIa | null>(null);
  const [falhaDoResumo, setFalhaDoResumo] = useState<string | null>(null);

  const formulario = useCarga(() => cliente.obterFormulario(formularioId), [cliente, formularioId]);
  const versoes = useCarga(() => cliente.listarVersoes(formularioId), [cliente, formularioId]);
  const consulta: ParametrosDeConsulta = {
    versaoId,
    criadoDe: criadoDe || undefined,
    criadoAte: criadoAte || undefined,
    filtros,
    meus: soMeus,
  };
  const contagens = useCarga(
    () => cliente.contagens(formularioId, consulta),
    [cliente, formularioId, versaoId, JSON.stringify(filtros), criadoDe, criadoAte, soMeus],
  );
  const listagem = useCarga(
    () =>
      cliente.listarRegistros(formularioId, {
        ...consulta,
        limite: POR_PAGINA,
        deslocamento: pagina * POR_PAGINA,
      }),
    [cliente, formularioId, versaoId, JSON.stringify(filtros), criadoDe, criadoAte, soMeus, pagina],
  );

  // Trocar de versão muda as colunas: filtros de campos de outra versão perdem o sentido.
  function trocarDeVersao(texto: string) {
    setVersaoId(texto === "" ? undefined : Number(texto));
    setFiltros({});
    setPagina(0);
  }

  async function exportar() {
    setFalhaDoCsv(null);
    try {
      baixarArquivo(await cliente.exportarRegistros(formularioId, consulta));
    } catch (erro) {
      setFalhaDoCsv(mensagemDe(erro));
    }
  }

  async function resumir() {
    setFalhaDoResumo(null);
    setResumo(null);
    try {
      setResumo(await cliente.resumir(formularioId, consulta));
    } catch (erro) {
      setFalhaDoResumo(erro instanceof ErroDaApi ? erro.message : mensagemDe(erro));
    }
  }

  const titulo = formulario.situacao === "pronto" ? formulario.dados.nome : "Registros";

  return (
    <section className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">Registros · {titulo}</h1>
        <ComPermissao permissao="registros:criar" bloqueado="Novo registro">
          <Botao
            variante="primario"
            onClick={() => navegar({ nome: "novoRegistro", formularioId })}
          >
            <Icone nome="mais" />
            Novo registro
          </Botao>
        </ComPermissao>
        <ComPermissao permissao="registros:exportar" bloqueado="Exportar CSV">
          <Botao onClick={() => void exportar()}>
            <Icone nome="baixar" />
            Exportar CSV
          </Botao>
        </ComPermissao>
        <ComPermissao permissao="ia:assistente">
          <Botao onClick={() => void resumir()}>
            <Icone nome="brilho" />
            Resumir com IA
          </Botao>
        </ComPermissao>
      </div>

      {contagens.situacao === "pronto" ? (
        <ChipsDeEstado
          contagens={contagens.dados}
          filtros={filtros}
          aoFiltrar={(novos) => {
            setFiltros(novos);
            setPagina(0);
          }}
        />
      ) : null}

      {resumo ? (
        <Cartao className="flex flex-col gap-2 p-4">
          <h2 className="font-bold">{resumo.titulo}</h2>
          {resumo.paragrafos.map((p, i) => (
            <p key={i} className="text-sm">
              {p}
            </p>
          ))}
          <p className="text-xs text-pedra-600">
            Redigido por IA a partir de números calculados pelo servidor e conferidos contra o
            banco.
          </p>
        </Cartao>
      ) : null}
      {falhaDoResumo ? <Falha mensagem={falhaDoResumo} /> : null}

      {falhaDoCsv ? <Falha mensagem={falhaDoCsv} /> : null}

      <details
        className="group rounded-cartao border border-pedra-200 bg-superficie shadow-cartao"
        open
      >
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-4 text-sm font-semibold sm:hidden">
          <Icone nome="funil" /> Filtros
        </summary>
        <Cartao className="flex flex-col gap-4 border-0 p-4 shadow-none">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
              Versão
              <select
                className={CLASSE_DO_CONTROLE}
                value={versaoId ?? ""}
                onChange={(e) => trocarDeVersao(e.target.value)}
              >
                <option value="">Última</option>
                {versoes.situacao === "pronto"
                  ? versoes.dados.map((versao) => (
                      <option key={versao.id} value={versao.id}>
                        Versão {versao.numero}
                      </option>
                    ))
                  : null}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
              Criado de
              <input
                type="date"
                className={CLASSE_DO_CONTROLE}
                value={criadoDe}
                onChange={(e) => {
                  setCriadoDe(e.target.value);
                  setPagina(0);
                }}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
              Criado até
              <input
                type="date"
                className={CLASSE_DO_CONTROLE}
                value={criadoAte}
                onChange={(e) => {
                  setCriadoAte(e.target.value);
                  setPagina(0);
                }}
              />
            </label>
            <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-pedra-800">
              <input
                type="checkbox"
                className="size-5 accent-sinal-500"
                checked={soMeus}
                onChange={(e) => {
                  setSoMeus(e.target.checked);
                  setPagina(0);
                }}
              />
              Só os meus
            </label>
          </div>

          {listagem.situacao === "pronto" ? (
            <FiltroPorCampo
              // Outra versão, outras colunas: recomeça o formulário de filtro.
              key={listagem.dados.versao_id}
              colunas={listagem.dados.colunas}
              filtros={filtros}
              aoMudar={(novos) => {
                setFiltros(novos);
                setPagina(0);
              }}
            />
          ) : null}
        </Cartao>
      </details>

      {listagem.situacao === "carregando" ? <EsqueletoDaTabela /> : null}
      {listagem.situacao === "erro" ? <Falha mensagem={listagem.mensagem} /> : null}
      {listagem.situacao === "pronto" ? (
        <Tabela
          colunas={listagem.dados.colunas}
          itens={listagem.dados.itens}
          total={listagem.dados.total}
          pagina={pagina}
          aoMudarDePagina={setPagina}
          exibicao={listagem.dados.exibicao ?? {}}
          abrir={(registroId) => navegar({ nome: "registro", registroId })}
        />
      ) : null}
    </section>
  );
}

function Tabela({
  colunas,
  itens,
  total,
  pagina,
  aoMudarDePagina,
  exibicao,
  abrir,
}: {
  exibicao: Esquemas["ExibicaoSaida"];
  colunas: Coluna[];
  itens: Esquemas["RegistroSaida"][];
  total: number;
  pagina: number;
  aoMudarDePagina: (pagina: number) => void;
  abrir: (registroId: number) => void;
}) {
  if (total === 0) {
    return (
      <EstadoVazio icone="registros" titulo="Nenhum registro encontrado.">
        Ajuste os filtros ou crie um registro novo.
      </EstadoVazio>
    );
  }
  const inicio = pagina * POR_PAGINA + 1;
  const fim = pagina * POR_PAGINA + itens.length;
  return (
    <>
      <CartoesDeRegistro colunas={colunas} itens={itens} exibicao={exibicao} abrir={abrir} />
      <Cartao className="hidden max-h-[70vh] overflow-auto sm:block">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-pedra-100 text-xs uppercase tracking-wide text-pedra-600">
            <tr>
              <th className="px-4 py-3 font-medium">#</th>
              {colunas.map((coluna) => (
                <th
                  key={coluna.id}
                  className={`px-4 py-3 font-medium ${eNumerica(coluna) ? "text-right" : ""}`}
                >
                  {coluna.rotulo}
                  {coluna.unidade ? ` (${coluna.unidade})` : ""}
                </th>
              ))}
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-pedra-200">
            {itens.map((registro) => (
              <tr
                key={registro.id}
                className="transition-colors duration-(--duracao-rapida) hover:bg-pedra-50"
              >
                <td className="px-4 py-3 font-mono text-pedra-500">{registro.id}</td>
                {colunas.map((coluna) => (
                  <td
                    key={coluna.id}
                    className={`px-4 py-3 ${eNumerica(coluna) ? "text-right font-mono tabular-nums" : ""}`}
                  >
                    {formatarCelula(coluna, registro.dados[coluna.id])}
                  </td>
                ))}
                <td className="px-4 py-3 text-right">
                  <Botao
                    variante="fantasma"
                    tamanho="pequeno"
                    aria-label={`Abrir o registro ${registro.id}`}
                    onClick={() => abrir(registro.id)}
                  >
                    Abrir
                  </Botao>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Cartao>
      <div className="flex items-center gap-3 text-sm text-pedra-600">
        <span className="mr-auto">
          Mostrando {inicio}–{fim} de {total}
        </span>
        <Botao
          tamanho="pequeno"
          disabled={pagina === 0}
          onClick={() => aoMudarDePagina(pagina - 1)}
        >
          Anterior
        </Botao>
        <Botao
          tamanho="pequeno"
          disabled={fim >= total}
          onClick={() => aoMudarDePagina(pagina + 1)}
        >
          Próxima
        </Botao>
      </div>
    </>
  );
}

/** No celular a lista vira cartões: o destaque em evidência, o estado ao lado e um resumo (§2.17). */
function CartoesDeRegistro({
  colunas,
  itens,
  exibicao,
  abrir,
}: {
  colunas: Coluna[];
  itens: Esquemas["RegistroSaida"][];
  exibicao: Esquemas["ExibicaoSaida"];
  abrir: (registroId: number) => void;
}) {
  const destaque = colunas.find((c) => c.id === exibicao.destaque);
  const resumo = (exibicao.resumo ?? [])
    .map((id) => colunas.find((c) => c.id === id))
    .filter((c): c is Coluna => c !== undefined);
  return (
    <ul className="flex flex-col gap-3 sm:hidden">
      {itens.map((r) => (
        <li key={r.id}>
          <button
            type="button"
            onClick={() => abrir(r.id)}
            className="flex w-full flex-col gap-1.5 rounded-cartao border border-pedra-200 bg-superficie p-4 text-left shadow-cartao"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm font-semibold">#{r.id}</span>
              <SeloDeEstado estado={r.estado} />
            </span>
            {destaque ? (
              <span className="font-mono text-2xl font-medium">
                {formatarCelula(destaque, r.dados[destaque.id]) || "—"}
                {destaque.unidade ? (
                  <span className="ml-1 text-sm text-pedra-600">{destaque.unidade}</span>
                ) : null}
              </span>
            ) : null}
            <span className="text-sm text-pedra-600">
              {resumo
                .map((c) => `${c.rotulo}: ${formatarCelula(c, r.dados[c.id]) || "—"}`)
                .join(" · ")}
              {r.criado_por ? `${resumo.length > 0 ? " · " : ""}por ${r.criado_por.nome}` : ""}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Os estados contados pelo servidor; Conforme e Não conforme filtram, os outros só informam. */
function ChipsDeEstado({
  contagens,
  filtros,
  aoFiltrar,
}: {
  contagens: Contagens;
  filtros: Record<string, string>;
  aoFiltrar: (filtros: Record<string, string>) => void;
}) {
  const campo = contagens.campo_status;
  const atual = campo ? filtros[campo] : undefined;
  const semStatus = Object.fromEntries(Object.entries(filtros).filter(([k]) => k !== campo));
  const chips: { rotulo: string; total: number; valor?: "true" | "false" | null }[] = [
    { rotulo: "Todos", total: contagens.total, valor: null },
    ...(campo
      ? [
          { rotulo: "Conformes", total: contagens.conforme, valor: "true" as const },
          { rotulo: "Não conformes", total: contagens.nao_conforme, valor: "false" as const },
          { rotulo: "Erro no cálculo", total: contagens.erro },
          { rotulo: "Aguardando dados", total: contagens.aguardando },
        ]
      : []),
  ];
  return (
    <div
      role="group"
      aria-label="Estado dos registros"
      className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0"
    >
      {chips.map((c) =>
        c.valor === undefined ? (
          <span
            key={c.rotulo}
            className="inline-flex min-h-11 shrink-0 items-center rounded-controle border border-pedra-200 bg-superficie px-4 text-sm text-pedra-600"
          >
            {c.rotulo} · {c.total}
          </span>
        ) : (
          <button
            key={c.rotulo}
            type="button"
            aria-pressed={c.valor === null ? atual === undefined : atual === c.valor}
            onClick={() =>
              aoFiltrar(
                c.valor === null || !campo ? semStatus : { ...semStatus, [campo]: c.valor ?? "" },
              )
            }
            className={`inline-flex min-h-11 shrink-0 items-center rounded-controle border px-4 text-sm font-semibold ${(c.valor === null ? atual === undefined : atual === c.valor) ? "border-pedra-900 bg-pedra-900 text-superficie" : "border-pedra-200 bg-superficie"}`}
          >
            {c.rotulo} · {c.total}
          </button>
        ),
      )}
    </div>
  );
}

/** Só oferece campo que a API aceita (`filtravel`): selecao, sim_nao, texto e calculado booleano. */
function FiltroPorCampo({
  colunas,
  filtros,
  aoMudar,
}: {
  colunas: Coluna[];
  filtros: Record<string, string>;
  aoMudar: (filtros: Record<string, string>) => void;
}) {
  const filtraveis = colunas.filter((coluna) => coluna.filtravel);
  const [campoId, setCampoId] = useState("");
  const [valor, setValor] = useState("");
  const coluna = filtraveis.find((c) => c.id === campoId);

  if (filtraveis.length === 0) return null;

  function aplicar() {
    if (!coluna || valor === "") return;
    aoMudar({ ...filtros, [coluna.id]: valor });
    setCampoId("");
    setValor("");
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-pedra-800">
          Filtrar por
          <select
            className={CLASSE_DO_CONTROLE}
            value={campoId}
            onChange={(e) => {
              setCampoId(e.target.value);
              setValor("");
            }}
          >
            <option value="">— campo —</option>
            {filtraveis.map((c) => (
              <option key={c.id} value={c.id}>
                {c.rotulo}
              </option>
            ))}
          </select>
        </label>
        {coluna ? <EntradaDoFiltro coluna={coluna} valor={valor} aoMudar={setValor} /> : null}
        <Botao disabled={!coluna || valor === ""} onClick={aplicar}>
          Aplicar filtro
        </Botao>
      </div>
      <ul className="flex flex-wrap gap-2">
        {Object.entries(filtros).map(([id, texto]) => {
          const rotulo = colunas.find((c) => c.id === id)?.rotulo ?? id;
          const restantes = Object.fromEntries(
            Object.entries(filtros).filter(([chave]) => chave !== id),
          );
          return (
            <li
              key={id}
              className="flex items-center gap-1.5 rounded-full border border-pedra-300 bg-pedra-100 py-0.5 pl-3 pr-1 text-sm"
            >
              {rotulo}: {rotuloDoValor(texto)}
              <button
                type="button"
                className="grid size-5 place-items-center rounded-full text-pedra-500 hover:bg-pedra-200 hover:text-pedra-900"
                aria-label={`Remover o filtro ${rotulo}`}
                onClick={() => aoMudar(restantes)}
              >
                <Icone nome="fechar" tamanho={12} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function EntradaDoFiltro({
  coluna,
  valor,
  aoMudar,
}: {
  coluna: Coluna;
  valor: string;
  aoMudar: (valor: string) => void;
}) {
  const classe = CLASSE_DO_CONTROLE;
  const booleano = coluna.tipo === "sim_nao" || coluna.resultado === "booleano";
  if (booleano) {
    return (
      <select
        aria-label="Valor do filtro"
        className={classe}
        value={valor}
        onChange={(e) => aoMudar(e.target.value)}
      >
        <option value="">— valor —</option>
        <option value="true">Sim</option>
        <option value="false">Não</option>
      </select>
    );
  }
  if (coluna.tipo === "selecao") {
    return (
      <select
        aria-label="Valor do filtro"
        className={classe}
        value={valor}
        onChange={(e) => aoMudar(e.target.value)}
      >
        <option value="">— valor —</option>
        {coluna.opcoes.map((opcao) => (
          <option key={opcao} value={opcao}>
            {opcao}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      aria-label="Valor do filtro"
      type="text"
      className={classe}
      value={valor}
      onChange={(e) => aoMudar(e.target.value)}
    />
  );
}

function rotuloDoValor(valor: string): string {
  return valor === "true" ? "Sim" : valor === "false" ? "Não" : valor;
}

/** Números alinham à direita, em fonte de largura fixa: as casas decimais ficam em coluna. */
function eNumerica(coluna: Coluna): boolean {
  return coluna.tipo === "numero" || (coluna.tipo === "calculado" && coluna.resultado === "numero");
}
