import type { Campo as CampoDaDefinicao, Definicao, ResultadoCalculado } from "../../api/cliente";
import { formatarNumero } from "../../lib/numero";
import { Campo, CLASSE_DO_CONTROLE } from "./Campo";
import { CampoDeFoto } from "./CampoDeFoto";
import { CampoDeLocalizacao } from "./CampoDeLocalizacao";
import { CampoDeReferencia } from "./CampoDeReferencia";
import type { Coordenadas, ErrosPorCampo, ValorDoCampo, Valores } from "./tipos";
import { useCalculosAoVivo } from "./useCalculosAoVivo";

interface Props {
  definicao: Definicao;
  valores: Valores;
  aoMudar: (valores: Valores) => void;
  /** Erros 422 da API, por `id` de campo. */
  erros?: ErrosPorCampo;
  /** `{valor, erro}` já gravados no registro; a prévia ao vivo os sobrepõe. */
  calculadosSalvos?: Record<string, ResultadoCalculado>;
  /** Pede a prévia dos calculados ao servidor enquanto o usuário digita (padrão: sim). */
  previaAoVivo?: boolean;
  somenteLeitura?: boolean;
  atrasoDaPreviaMs?: number;
}

/**
 * Renderiza qualquer versão de formulário a partir da definição, sempre por `id` (nunca por
 * índice, que muda quando o construtor reordena). Não valida nem calcula: mostra o que o
 * servidor devolve (AGENTS.md §2.4).
 */
export function FormRenderer({
  definicao,
  valores,
  aoMudar,
  erros = {},
  calculadosSalvos = {},
  previaAoVivo = true,
  somenteLeitura = false,
  atrasoDaPreviaMs,
}: Props) {
  const aoVivo = useCalculosAoVivo(definicao, valores, {
    habilitado: previaAoVivo && !somenteLeitura,
    atrasoMs: atrasoDaPreviaMs,
  });
  const calculados = { ...calculadosSalvos, ...aoVivo.calculados };

  function mudar(id: string, valor: ValorDoCampo) {
    aoMudar({ ...valores, [id]: valor });
  }

  return (
    <div className="flex flex-col gap-4">
      {definicao.campos.map((campo) => {
        const errosDoCampo = erros[campo.id];
        const comum = { somenteLeitura, erros: errosDoCampo };
        switch (campo.tipo) {
          case "secao":
            return (
              <h2
                key={campo.id}
                className="mt-2 border-b border-pedra-300 pb-1 text-lg font-semibold"
              >
                {campo.rotulo}
              </h2>
            );
          case "calculado":
            return <CampoCalculado key={campo.id} campo={campo} resultado={calculados[campo.id]} />;
          case "referencia":
            return (
              <CampoDeReferencia
                key={campo.id}
                campo={campo}
                valor={asNumero(valores[campo.id])}
                aoMudar={(valor) => mudar(campo.id, valor)}
                {...comum}
              />
            );
          case "localizacao":
            return (
              <CampoDeLocalizacao
                key={campo.id}
                campo={campo}
                valor={asCoordenadas(valores[campo.id])}
                aoMudar={(valor) => mudar(campo.id, valor)}
                {...comum}
              />
            );
          case "foto":
            return (
              <CampoDeFoto
                key={campo.id}
                campo={campo}
                valor={asLista(valores[campo.id])}
                aoMudar={(valor) => mudar(campo.id, valor)}
                {...comum}
              />
            );
          default:
            return (
              <CampoSimples
                key={campo.id}
                campo={campo}
                valor={valores[campo.id]}
                aoMudar={(valor) => mudar(campo.id, valor)}
                {...comum}
              />
            );
        }
      })}
      {aoVivo.indisponivel ? (
        <p className="text-sm text-amber-700">
          Não foi possível atualizar a prévia dos campos calculados.
        </p>
      ) : null}
    </div>
  );
}

interface PropsSimples {
  campo: CampoDaDefinicao;
  valor: ValorDoCampo;
  erros?: string[];
  somenteLeitura: boolean;
  aoMudar: (valor: ValorDoCampo) => void;
}

/** texto, número, data, seleção e sim/não: um controle nativo cada. */
function CampoSimples({ campo, valor, erros, somenteLeitura, aoMudar }: PropsSimples) {
  return (
    <Campo
      id={campo.id}
      rotulo={campo.rotulo}
      unidade={campo.unidade}
      obrigatorio={campo.obrigatorio}
      erros={erros}
    >
      {(propsDoControle) => {
        switch (campo.tipo) {
          case "selecao":
            return (
              <select
                {...propsDoControle}
                className={CLASSE_DO_CONTROLE}
                disabled={somenteLeitura}
                value={asTexto(valor)}
                onChange={(e) => aoMudar(e.target.value)}
              >
                <option value="">— selecione —</option>
                {(campo.opcoes ?? []).map((opcao) => (
                  <option key={opcao} value={opcao}>
                    {opcao}
                  </option>
                ))}
              </select>
            );
          case "sim_nao":
            return (
              <select
                {...propsDoControle}
                className={CLASSE_DO_CONTROLE}
                disabled={somenteLeitura}
                value={valor === true ? "sim" : valor === false ? "nao" : ""}
                onChange={(e) => aoMudar(e.target.value === "" ? null : e.target.value === "sim")}
              >
                <option value="">— não informado —</option>
                <option value="sim">Sim</option>
                <option value="nao">Não</option>
              </select>
            );
          case "data":
            return (
              <input
                {...propsDoControle}
                type="date"
                className={CLASSE_DO_CONTROLE}
                disabled={somenteLeitura}
                value={asTexto(valor)}
                onChange={(e) => aoMudar(e.target.value)}
              />
            );
          case "numero":
            return (
              <input
                {...propsDoControle}
                type="text"
                inputMode="decimal"
                className={CLASSE_DO_CONTROLE}
                disabled={somenteLeitura}
                value={asTexto(valor)}
                // A API espera ponto decimal; quem digita em português usa vírgula.
                onChange={(e) => aoMudar(e.target.value.replace(",", "."))}
              />
            );
          default:
            return (
              <input
                {...propsDoControle}
                type="text"
                className={CLASSE_DO_CONTROLE}
                disabled={somenteLeitura}
                value={asTexto(valor)}
                onChange={(e) => aoMudar(e.target.value)}
              />
            );
        }
      }}
    </Campo>
  );
}

function CampoCalculado({
  campo,
  resultado,
}: {
  campo: CampoDaDefinicao;
  resultado: ResultadoCalculado | undefined;
}) {
  const id = `campo-${campo.id}`;
  return (
    <div className="flex flex-col gap-1" data-campo={campo.id}>
      <span id={`${id}-rotulo`} className="text-sm font-medium text-pedra-700">
        {campo.rotulo}
        {campo.unidade ? (
          <span className="ml-1 font-normal text-pedra-500">({campo.unidade})</span>
        ) : null}
      </span>
      <output
        id={id}
        aria-labelledby={`${id}-rotulo`}
        className={`rounded-controle border px-3 py-2 text-sm ${
          resultado?.erro
            ? "border-erro-300 bg-erro-50 text-erro-700"
            : "border-pedra-200 bg-pedra-50 text-pedra-800"
        }`}
      >
        {resultado?.erro
          ? resultado.erro
          : formatarCalculado(resultado?.valor, campo.casas_decimais)}
      </output>
    </div>
  );
}

/** Exibição: `casas_decimais` arredonda só o que se vê; o valor guardado mantém a precisão. */
function formatarCalculado(
  valor: string | boolean | null | undefined,
  casas: number | null | undefined,
) {
  if (valor === null || valor === undefined) return "—";
  if (typeof valor === "boolean") return valor ? "Sim" : "Não";
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return valor.split("-").reverse().join("/");
  if (/^[+-]?\d+(\.\d+)?$/.test(valor)) return formatarNumero(valor, casas);
  return valor;
}

function asTexto(valor: ValorDoCampo): string {
  return typeof valor === "string" ? valor : "";
}

function asNumero(valor: ValorDoCampo): number | null {
  return typeof valor === "number" ? valor : null;
}

function asLista(valor: ValorDoCampo): number[] {
  return Array.isArray(valor) ? valor : [];
}

function asCoordenadas(valor: ValorDoCampo): Coordenadas | null {
  return valor !== null && typeof valor === "object" && !Array.isArray(valor) ? valor : null;
}
