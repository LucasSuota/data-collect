import { useEffect, useRef, useState } from "react";
import { useApi } from "../../api/contexto";
import { ErroDaApi, type Campo as CampoDaDefinicao } from "../../api/cliente";
import { Campo } from "./Campo";

interface Props {
  campo: CampoDaDefinicao;
  /** Os `id`s dos anexos: é só isto que o registro guarda. */
  valor: number[] | null | undefined;
  erros?: string[];
  somenteLeitura?: boolean;
  aoMudar: (ids: number[]) => void;
}

/** Envia a foto (`POST /anexos`), mostra a miniatura e guarda só os `id`s. Sem câmera direta. */
export function CampoDeFoto({ campo, valor, erros, somenteLeitura, aoMudar }: Props) {
  const cliente = useApi();
  const ids = valor ?? [];
  const entrada = useRef<HTMLInputElement>(null);
  const [enviando, setEnviando] = useState(false);
  const [falha, setFalha] = useState<string | null>(null);
  const cheio = campo.maximo != null && ids.length >= campo.maximo;

  async function enviar(arquivos: FileList | null) {
    const escolhidos = Array.from(arquivos ?? []);
    if (escolhidos.length === 0) return;
    setEnviando(true);
    setFalha(null);
    let atuais = ids;
    try {
      for (const arquivo of escolhidos) {
        if (campo.maximo != null && atuais.length >= campo.maximo) break;
        const anexo = await cliente.enviarAnexo(arquivo);
        atuais = [...atuais, anexo.id];
        aoMudar(atuais);
      }
    } catch (erro) {
      // 422 traz o motivo em português (formato inválido, HEIC, acima de 20 MB...).
      setFalha(
        erro instanceof ErroDaApi
          ? (erro.erros[0]?.mensagem ?? erro.message)
          : "Falha ao enviar a foto.",
      );
    } finally {
      setEnviando(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  return (
    <Campo id={campo.id} rotulo={campo.rotulo} obrigatorio={campo.obrigatorio} erros={erros}>
      {(propsDoControle) => (
        <div className="flex flex-col gap-2">
          <ul className="flex flex-wrap gap-2">
            {ids.map((id) => (
              <li key={id} className="relative">
                <Miniatura anexoId={id} rotulo={campo.rotulo} />
                {somenteLeitura ? null : (
                  <button
                    type="button"
                    aria-label={`Remover foto ${id}`}
                    className="absolute -right-2 -top-2 rounded-full bg-red-600 px-1.5 text-xs text-white"
                    onClick={() => aoMudar(ids.filter((outro) => outro !== id))}
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
          {somenteLeitura ? null : (
            <input
              {...propsDoControle}
              ref={entrada}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple={campo.maximo == null || campo.maximo > 1}
              disabled={cheio || enviando}
              onChange={(evento) => void enviar(evento.target.files)}
              className="text-sm"
            />
          )}
          {enviando ? <p className="text-sm text-slate-500">Enviando…</p> : null}
          {cheio ? (
            <p className="text-sm text-slate-500">Limite de {campo.maximo} foto(s) atingido.</p>
          ) : null}
          {falha ? (
            <p role="alert" className="text-sm text-red-700">
              {falha}
            </p>
          ) : null}
        </div>
      )}
    </Campo>
  );
}

/** A imagem vem por `fetch` (com o token) e vira uma URL local: `<img src>` não manda cabeçalho. */
function Miniatura({ anexoId, rotulo }: { anexoId: number; rotulo: string }) {
  const cliente = useApi();
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    let criada: string | null = null;
    cliente.obterAnexo(anexoId).then(
      (blob) => {
        if (cancelado) return;
        criada = URL.createObjectURL(blob);
        setUrl(criada);
      },
      () => undefined,
    );
    return () => {
      cancelado = true;
      if (criada) URL.revokeObjectURL(criada);
    };
  }, [cliente, anexoId]);

  return url ? (
    <img src={url} alt={`${rotulo}: foto ${anexoId}`} className="h-20 w-20 rounded object-cover" />
  ) : (
    <div
      className="h-20 w-20 animate-pulse rounded bg-slate-200"
      role="img"
      aria-label="Carregando foto"
    />
  );
}
