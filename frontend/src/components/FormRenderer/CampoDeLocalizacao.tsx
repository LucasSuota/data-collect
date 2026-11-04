import { useState } from "react";
import type { Campo as CampoDaDefinicao } from "../../api/cliente";
import { Icone } from "../../ui";
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
  const [aviso, setAviso] = useState<string | null>(null);
  const [buscando, setBuscando] = useState(false);

  /** Só sob gesto da pessoa (clique), com mensagem clara se a permissão for negada (AGENTS.md §2.8). */
  function usarMinhaLocalizacao() {
    setAviso(null);
    if (!("geolocation" in navigator)) {
      setAviso("Este aparelho não informa a localização. Digite as coordenadas.");
      return;
    }
    setBuscando(true);
    navigator.geolocation.getCurrentPosition(
      (posicao) => {
        setBuscando(false);
        aoMudar({
          latitude: posicao.coords.latitude.toFixed(6),
          longitude: posicao.coords.longitude.toFixed(6),
        });
      },
      (erro) => {
        setBuscando(false);
        setAviso(
          erro.code === erro.PERMISSION_DENIED
            ? "A permissão de localização foi negada. Libere nas configurações do navegador ou digite as coordenadas."
            : "Não foi possível obter a localização agora. Tente de novo ou digite as coordenadas.",
        );
      },
      { enableHighAccuracy: true, timeout: 15_000 },
    );
  }

  return (
    <Campo id={campo.id} rotulo={campo.rotulo} obrigatorio={campo.obrigatorio} erros={erros}>
      {(propsDoControle) => (
        <div className="grid grid-cols-2 gap-2">
          {!somenteLeitura ? (
            <button
              type="button"
              onClick={usarMinhaLocalizacao}
              disabled={buscando}
              className="col-span-2 inline-flex min-h-11 items-center justify-center gap-2 rounded-controle border border-pedra-300 bg-superficie text-sm font-semibold hover:bg-pedra-100 disabled:opacity-60"
            >
              <Icone nome="pino" />
              {buscando ? "Buscando localização…" : "Usar minha localização"}
            </button>
          ) : null}
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
          {aviso ? (
            <p role="status" className="col-span-2 text-sm text-aviso-700">
              {aviso}
            </p>
          ) : null}
        </div>
      )}
    </Campo>
  );
}

/** A API espera ponto decimal; quem digita em português usa vírgula. */
function normalizar(texto: string): string {
  return texto.replace(",", ".");
}
