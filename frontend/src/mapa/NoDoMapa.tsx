import { Conformidade, Icone, type NomeDoIcone } from "../ui";
import type { LinhaDoNo, NoDoGrafo } from "./grafo";
import { ALTURA_DA_LINHA, ALTURA_DO_CABECALHO, LARGURA_DO_NO, alturaDoNo } from "./medidas";

interface Props {
  no: NoDoGrafo;
  x: number;
  y: number;
  selecionado: boolean;
  /** Fora da cadeia do nó selecionado: fica apagado para a cadeia saltar à vista. */
  esmaecido: boolean;
  aoSelecionar: () => void;
}

const ICONE_DA_LINHA: Partial<Record<LinhaDoNo["tipo"], NomeDoIcone>> = {
  entrada: "entrada",
  compartilhado: "elo",
};

/** Um cartão do mapa: cabeçalho (o que é) e linhas (de onde vem, o que libera, os valores). */
export function NoDoMapa({ no, x, y, selecionado, esmaecido, aoSelecionar }: Props) {
  const altura = alturaDoNo(no);
  const descricao =
    no.tipo === "formulario"
      ? `Formulário ${no.titulo}, ${no.subtitulo}`
      : `Registro ${no.registroId} de ${no.titulo}`;

  return (
    <div
      data-no={no.id}
      className={`absolute transition-opacity duration-(--duracao-normal) ${esmaecido ? "opacity-35" : ""}`}
      style={{ left: x, top: y, width: LARGURA_DO_NO, height: altura }}
    >
      <button
        type="button"
        aria-label={descricao}
        aria-pressed={selecionado}
        onClick={aoSelecionar}
        className={`block h-full w-full overflow-hidden rounded-cartao border bg-superficie text-left shadow-cartao transition-shadow duration-(--duracao-rapida) hover:shadow-elevada ${selecionado ? "border-sinal-500 ring-2 ring-sinal-500/30" : "border-pedra-300"}`}
      >
        <span
          className="flex items-center gap-2.5 border-b border-pedra-200 bg-pedra-50 px-3"
          style={{ height: ALTURA_DO_CABECALHO }}
        >
          <span
            className={`grid size-8 shrink-0 place-items-center rounded-controle ${no.tipo === "formulario" ? "bg-pedra-900 text-superficie" : "bg-pedra-200 text-pedra-700"}`}
          >
            <Icone nome={no.tipo === "formulario" ? "registros" : "pasta"} />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm leading-tight font-semibold">{no.titulo}</span>
            <span className="block truncate font-mono text-xs leading-tight text-pedra-500 tabular-nums">
              {no.subtitulo}
            </span>
          </span>
        </span>
        <span className="block">
          {no.linhas.map((linha) => (
            <Linha key={`${linha.tipo}-${linha.chave}`} linha={linha} />
          ))}
          {no.linhasOcultas > 0 ? (
            <span className="block px-3 py-1 text-xs text-pedra-500">
              +{no.linhasOcultas} {no.linhasOcultas === 1 ? "campo" : "campos"}
            </span>
          ) : null}
        </span>
      </button>
      <Porta lado="esquerda" altura={altura} />
      <Porta lado="direita" altura={altura} />
    </div>
  );
}

/** Os pontos de ligação, como as portas de um nó do n8n. */
function Porta({ lado, altura }: { lado: "esquerda" | "direita"; altura: number }) {
  return (
    <span
      aria-hidden="true"
      className="absolute size-3 rounded-full border-2 border-pedra-500 bg-superficie"
      style={{ top: altura / 2 - 6, [lado === "esquerda" ? "left" : "right"]: -6 }}
    />
  );
}

function Linha({ linha }: { linha: LinhaDoNo }) {
  const icone = ICONE_DA_LINHA[linha.tipo];
  return (
    <span
      className="flex items-center gap-2 px-3 text-[0.8125rem]"
      style={{ height: ALTURA_DA_LINHA }}
    >
      {icone ? (
        <Icone
          nome={icone}
          tamanho={13}
          className={
            linha.tipo === "compartilhado" ? "shrink-0 text-sinal-600" : "shrink-0 text-pedra-500"
          }
        />
      ) : (
        <span className="size-[13px] shrink-0" aria-hidden="true" />
      )}
      <span className="min-w-0 flex-1 truncate text-pedra-600">{linha.rotulo}</span>
      <Valor linha={linha} />
    </span>
  );
}

function Valor({ linha }: { linha: LinhaDoNo }) {
  if (linha.tipo === "conformidade" && linha.conforme !== null) {
    return <Conformidade conforme={linha.conforme} texto={linha.valor} />;
  }
  if (linha.tipo === "entrada") {
    return (
      <span className="max-w-[9rem] truncate rounded-controle bg-pedra-100 px-1.5 py-0.5 text-xs font-medium text-pedra-700">
        {linha.valor}
      </span>
    );
  }
  return (
    <span className="max-w-[10rem] shrink-0 truncate font-mono text-pedra-900 tabular-nums">
      {linha.valor === "" ? "—" : linha.valor}
      {linha.unidade && linha.valor !== linha.unidade ? (
        <span className="ml-1 text-xs text-pedra-500">{linha.unidade}</span>
      ) : null}
    </span>
  );
}
