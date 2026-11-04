import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Botao } from "./Botao";
import { Icone } from "./Icone";

interface Props {
  titulo: string;
  subtitulo?: string;
  /** Quantas gavetas há por baixo: cada uma abre um pouco mais à esquerda, e a de baixo aparece. */
  profundidade?: number;
  aoFechar: () => void;
  /** Clicar fora fecha. Só para gavetas sem nada a perder (uma lista, não um formulário). */
  fecharAoClicarFora?: boolean;
  children: ReactNode;
}

const FOCAVEIS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const AFASTAMENTO_POR_NIVEL = 32;

/**
 * Painel lateral modal: o foco entra nele, Tab não escapa, Esc fecha e o foco volta ao que
 * estava antes. Vai para o `body` (portal), então um `<form>` dentro dele não fica dentro do
 * formulário da tela de baixo.
 */
export function Gaveta({
  titulo,
  subtitulo,
  profundidade = 0,
  aoFechar,
  fecharAoClicarFora = false,
  children,
}: Props) {
  const painel = useRef<HTMLDivElement>(null);
  const idDoTitulo = useId();

  useEffect(() => {
    const anterior = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    painel.current?.focus();
    return () => anterior?.focus();
  }, []);

  function aoTeclar(evento: KeyboardEvent<HTMLDivElement>) {
    if (evento.key === "Escape") {
      // Uma gaveta dentro de outra: o Esc é só da de cima.
      evento.stopPropagation();
      aoFechar();
      return;
    }
    if (evento.key !== "Tab" || !painel.current) return;
    evento.stopPropagation();
    const focaveis = [...painel.current.querySelectorAll<HTMLElement>(FOCAVEIS)];
    const primeiro = focaveis[0];
    const ultimo = focaveis[focaveis.length - 1];
    if (!primeiro || !ultimo) return;
    const ativo = document.activeElement;
    if (evento.shiftKey && (ativo === primeiro || ativo === painel.current)) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && ativo === ultimo) {
      evento.preventDefault();
      primeiro.focus();
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 bg-pedra-900/45"
      onMouseDown={(evento) => {
        if (fecharAoClicarFora && evento.target === evento.currentTarget) aoFechar();
      }}
    >
      <div
        ref={painel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idDoTitulo}
        tabIndex={-1}
        onKeyDown={aoTeclar}
        className="absolute inset-y-0 flex w-full max-w-xl flex-col bg-papel shadow-elevada outline-none"
        style={{ right: profundidade * AFASTAMENTO_POR_NIVEL }}
      >
        <header className="flex items-start gap-3 border-b border-pedra-200 bg-superficie px-5 py-4">
          <div className="min-w-0 flex-1">
            <h2 id={idDoTitulo} className="truncate text-lg font-semibold tracking-tight">
              {titulo}
            </h2>
            {subtitulo ? <p className="text-sm text-pedra-600">{subtitulo}</p> : null}
          </div>
          <Botao variante="fantasma" tamanho="pequeno" aria-label="Fechar" onClick={aoFechar}>
            <Icone nome="fechar" />
          </Botao>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
