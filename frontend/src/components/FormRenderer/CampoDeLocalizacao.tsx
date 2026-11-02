import type { Campo as CampoDaDefinicao } from "../../api/cliente";
import { Campo, CLASSE_DO_CONTROLE } from "./Campo";
import type { Coordenadas } from "./tipos";

interface Props {
  campo: CampoDaDefinicao;
  valor: Coordenadas | null | undefined;
  erros?: string[];
  somenteLeitura?: boolean;
  aoMudar: (valor: Coordenadas) => void;
}

/** Latitude e longitude como texto. A validação da faixa é do servidor (AGENTS.md §2.8). */
export function CampoDeLocalizacao({ campo, valor, erros, somenteLeitura, aoMudar }: Props) {
  const atual: Coordenadas = { latitude: valor?.latitude ?? "", longitude: valor?.longitude ?? "" };
  return (
    <Campo id={campo.id} rotulo={campo.rotulo} obrigatorio={campo.obrigatorio} erros={erros}>
      {(propsDoControle) => (
        <div className="grid grid-cols-2 gap-2">
          <input
            {...propsDoControle}
            type="text"
            inputMode="decimal"
            aria-label={`${campo.rotulo}: latitude`}
            placeholder="Latitude"
            className={CLASSE_DO_CONTROLE}
            disabled={somenteLeitura}
            value={atual.latitude}
            onChange={(e) => aoMudar({ ...atual, latitude: normalizar(e.target.value) })}
          />
          <input
            type="text"
            inputMode="decimal"
            aria-label={`${campo.rotulo}: longitude`}
            aria-invalid={propsDoControle["aria-invalid"]}
            placeholder="Longitude"
            className={CLASSE_DO_CONTROLE}
            disabled={somenteLeitura}
            value={atual.longitude}
            onChange={(e) => aoMudar({ ...atual, longitude: normalizar(e.target.value) })}
          />
        </div>
      )}
    </Campo>
  );
}

/** A API espera ponto decimal; quem digita em português usa vírgula. */
function normalizar(texto: string): string {
  return texto.replace(",", ".");
}
