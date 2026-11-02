import { useState } from "react";
import { useApi } from "../api/contexto";
import type { Esquemas, ParametrosDeConsulta } from "../api/cliente";
import { baixarArquivo, formatarCelula } from "../lib/formatacao";
import type { Rota } from "../rotas";
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

  const formulario = useCarga(() => cliente.obterFormulario(formularioId), [cliente, formularioId]);
  const versoes = useCarga(() => cliente.listarVersoes(formularioId), [cliente, formularioId]);
  const consulta: ParametrosDeConsulta = {
    versaoId,
    criadoDe: criadoDe || undefined,
    criadoAte: criadoAte || undefined,
    filtros,
  };
  const listagem = useCarga(
    () =>
      cliente.listarRegistros(formularioId, {
        ...consulta,
        limite: POR_PAGINA,
        deslocamento: pagina * POR_PAGINA,
      }),
    [cliente, formularioId, versaoId, JSON.stringify(filtros), criadoDe, criadoAte, pagina],
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

  const titulo = formulario.situacao === "pronto" ? formulario.dados.nome : "Registros";

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Registros · {titulo}</h1>
        <button
          type="button"
          className="rounded bg-pedra-900 px-3 py-1.5 text-white"
          onClick={() => navegar({ nome: "novoRegistro", formularioId })}
        >
          Novo registro
        </button>
        <button
          type="button"
          className="rounded border border-pedra-300 px-3 py-1.5"
          onClick={() => void exportar()}
        >
          Exportar CSV
        </button>
      </div>

      {falhaDoCsv ? <Falha mensagem={falhaDoCsv} /> : null}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm">
          Versão
          <select
            className="rounded border border-pedra-300 px-2 py-1.5"
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
        <label className="flex flex-col text-sm">
          Criado de
          <input
            type="date"
            className="rounded border border-pedra-300 px-2 py-1.5"
            value={criadoDe}
            onChange={(e) => {
              setCriadoDe(e.target.value);
              setPagina(0);
            }}
          />
        </label>
        <label className="flex flex-col text-sm">
          Criado até
          <input
            type="date"
            className="rounded border border-pedra-300 px-2 py-1.5"
            value={criadoAte}
            onChange={(e) => {
              setCriadoAte(e.target.value);
              setPagina(0);
            }}
          />
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

      {listagem.situacao === "carregando" ? <EsqueletoDaTabela /> : null}
      {listagem.situacao === "erro" ? <Falha mensagem={listagem.mensagem} /> : null}
      {listagem.situacao === "pronto" ? (
        <Tabela
          colunas={listagem.dados.colunas}
          itens={listagem.dados.itens}
          total={listagem.dados.total}
          pagina={pagina}
          aoMudarDePagina={setPagina}
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
  abrir,
}: {
  colunas: Coluna[];
  itens: Esquemas["RegistroSaida"][];
  total: number;
  pagina: number;
  aoMudarDePagina: (pagina: number) => void;
  abrir: (registroId: number) => void;
}) {
  if (total === 0) {
    return <p className="text-pedra-600">Nenhum registro encontrado.</p>;
  }
  const inicio = pagina * POR_PAGINA + 1;
  const fim = pagina * POR_PAGINA + itens.length;
  return (
    <>
      <div className="overflow-x-auto rounded border border-pedra-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-pedra-50">
            <tr>
              <th className="p-2">#</th>
              {colunas.map((coluna) => (
                <th key={coluna.id} className="p-2">
                  {coluna.rotulo}
                  {coluna.unidade ? ` (${coluna.unidade})` : ""}
                </th>
              ))}
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {itens.map((registro) => (
              <tr key={registro.id} className="border-t border-pedra-100">
                <td className="p-2">{registro.id}</td>
                {colunas.map((coluna) => (
                  <td key={coluna.id} className="p-2">
                    {formatarCelula(coluna, registro.dados[coluna.id])}
                  </td>
                ))}
                <td className="p-2">
                  <button
                    type="button"
                    className="underline"
                    aria-label={`Abrir o registro ${registro.id}`}
                    onClick={() => abrir(registro.id)}
                  >
                    Abrir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span>
          Mostrando {inicio}–{fim} de {total}
        </span>
        <button
          type="button"
          className="rounded border border-pedra-300 px-2 py-1 disabled:opacity-50"
          disabled={pagina === 0}
          onClick={() => aoMudarDePagina(pagina - 1)}
        >
          Anterior
        </button>
        <button
          type="button"
          className="rounded border border-pedra-300 px-2 py-1 disabled:opacity-50"
          disabled={fim >= total}
          onClick={() => aoMudarDePagina(pagina + 1)}
        >
          Próxima
        </button>
      </div>
    </>
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
        <label className="flex flex-col text-sm">
          Filtrar por
          <select
            className="rounded border border-pedra-300 px-2 py-1.5"
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
        <button
          type="button"
          className="rounded border border-pedra-300 px-3 py-1.5 disabled:opacity-50"
          disabled={!coluna || valor === ""}
          onClick={aplicar}
        >
          Aplicar filtro
        </button>
      </div>
      <ul className="flex flex-wrap gap-2">
        {Object.entries(filtros).map(([id, texto]) => {
          const rotulo = colunas.find((c) => c.id === id)?.rotulo ?? id;
          const restantes = Object.fromEntries(
            Object.entries(filtros).filter(([chave]) => chave !== id),
          );
          return (
            <li key={id} className="rounded-full bg-pedra-100 px-3 py-1 text-sm">
              {rotulo}: {rotuloDoValor(texto)}
              <button
                type="button"
                className="ml-2"
                aria-label={`Remover o filtro ${rotulo}`}
                onClick={() => aoMudar(restantes)}
              >
                ×
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
  const classe = "rounded border border-pedra-300 px-2 py-1.5";
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
