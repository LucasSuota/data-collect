import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import type { Registro } from "../api/cliente";
import { Falha } from "../paginas/Estado";
import { Carregando, Esqueleto, Gaveta } from "../ui";
import { ContextoDeGavetas, type PedidoDeGaveta } from "./contexto";
import { EditorDeRegistro } from "./EditorDeRegistro";
import { useRegistroCarregado } from "./useRegistroCarregado";

type Aberta = PedidoDeGaveta & { chave: number };

/**
 * Guarda a pilha de gavetas de registro. Um campo de referência pede "criar/editar a origem
 * aqui" e continua onde estava; a origem pode ela mesma depender de outra, e a pilha cresce
 * (Insitu → Proctor → Ensaio) sem perder o que já foi digitado em cada nível.
 */
export function ProvedorDeGavetas({ children }: { children: ReactNode }) {
  const [pilha, setPilha] = useState<Aberta[]>([]);
  const proxima = useRef(0);
  const abrir = useCallback(
    (pedido: PedidoDeGaveta) =>
      setPilha((atual) => [...atual, { ...pedido, chave: proxima.current++ }]),
    [],
  );
  const valor = useMemo(() => ({ abrir }), [abrir]);
  const fechar = (chave: number) => setPilha((atual) => atual.filter((g) => g.chave !== chave));

  return (
    <ContextoDeGavetas.Provider value={valor}>
      {children}
      {pilha.map((aberta, indice) => (
        <GavetaDeRegistro
          key={aberta.chave}
          pedido={aberta}
          profundidade={indice}
          total={pilha.length}
          aoFechar={() => fechar(aberta.chave)}
          aoSalvar={(registro) => {
            fechar(aberta.chave);
            aberta.aoConcluir(registro);
          }}
        />
      ))}
    </ContextoDeGavetas.Provider>
  );
}

function GavetaDeRegistro({
  pedido,
  profundidade,
  total,
  aoFechar,
  aoSalvar,
}: {
  pedido: PedidoDeGaveta;
  profundidade: number;
  total: number;
  aoFechar: () => void;
  aoSalvar: (registro: Registro) => void;
}) {
  const carga = useRegistroCarregado(pedido.modo);
  const titulo =
    carga.situacao !== "pronto"
      ? "Carregando…"
      : `${carga.dados.registro ? `Registro ${carga.dados.registro.id}` : "Novo registro"} · ${carga.dados.nomeDoFormulario}`;

  return (
    <Gaveta
      titulo={titulo}
      subtitulo={total > 1 ? `Etapa ${profundidade + 1} de ${total}` : undefined}
      profundidade={profundidade}
      aoFechar={aoFechar}
    >
      {carga.situacao === "carregando" ? (
        <Carregando rotulo="Carregando o formulário">
          <Esqueleto className="h-40 w-full" />
        </Carregando>
      ) : null}
      {carga.situacao === "erro" ? <Falha mensagem={carga.mensagem} /> : null}
      {carga.situacao === "pronto" ? (
        <EditorDeRegistro carregado={carga.dados} aoSalvar={aoSalvar} aoCancelar={aoFechar} />
      ) : null}
    </Gaveta>
  );
}
