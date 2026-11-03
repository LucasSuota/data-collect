import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { Botao, Icone } from "../ui";
import { ajustarAoQuadro, zoomEm, type Vista } from "./geometria";

interface Props {
  /** O tamanho do conteúdo, em pixels não escalados. */
  conteudo: { largura: number; altura: number };
  /** Muda quando o conteúdo é outro: a vista volta a ajustar-se à tela. */
  chave: string;
  rotulo: string;
  children: ReactNode;
}

const QUADRO_PADRAO = { largura: 900, altura: 560 };
const PASSO_DO_ZOOM = 1.2;
const PASSO_DO_TECLADO = 60;

/**
 * Área do mapa com arrastar para mover e zoom, como o canvas do n8n: arrastar o fundo move,
 * Ctrl/⌘ + roda (ou pinça) dá zoom, a roda sozinha move. Pelo teclado: setas movem, + e − dão
 * zoom e 0 ajusta à tela. O fundo pontilhado acompanha o movimento e o zoom.
 */
export function Quadro({ conteudo, chave, rotulo, children }: Props) {
  const area = useRef<HTMLDivElement>(null);
  const [tamanho, setTamanho] = useState(QUADRO_PADRAO);
  // Enquanto a pessoa não mexe, a vista é a ajustada (derivada); mexer a "congela" nesta chave.
  const [manual, setManual] = useState<{ chave: string; vista: Vista } | null>(null);
  const arrasto = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const elemento = area.current;
    if (!elemento) return;
    const medir = () => {
      const { width, height } = elemento.getBoundingClientRect();
      if (width > 0 && height > 0) setTamanho({ largura: width, altura: height });
    };
    // Medida inicial própria: o observador só avisa de mudanças e a vista precisa do tamanho real já.
    const quadro = requestAnimationFrame(medir);
    if (typeof ResizeObserver === "undefined") return () => cancelAnimationFrame(quadro);
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => {
      cancelAnimationFrame(quadro);
      observador.disconnect();
    };
  }, []);

  const ajustada = ajustarAoQuadro(conteudo, tamanho);
  const vista = manual?.chave === chave ? manual.vista : ajustada;
  const mudar = (nova: Vista) => setManual({ chave, vista: nova });
  const centro = { x: tamanho.largura / 2, y: tamanho.altura / 2 };

  useEffect(() => {
    const elemento = area.current;
    if (!elemento) return;
    // Nativo e não passivo: o React registra `onWheel` como passivo e não deixaria impedir a rolagem da página.
    const aoRolar = (evento: WheelEvent) => {
      evento.preventDefault();
      const caixa = elemento.getBoundingClientRect();
      if (evento.ctrlKey || evento.metaKey) {
        const fator = Math.exp(-evento.deltaY * 0.01);
        setManual({
          chave,
          vista: zoomEm(
            vista,
            { x: evento.clientX - caixa.left, y: evento.clientY - caixa.top },
            fator,
          ),
        });
      } else {
        setManual({
          chave,
          vista: { ...vista, x: vista.x - evento.deltaX, y: vista.y - evento.deltaY },
        });
      }
    };
    elemento.addEventListener("wheel", aoRolar, { passive: false });
    return () => elemento.removeEventListener("wheel", aoRolar);
  }, [chave, vista]);

  function aoPressionar(evento: PointerEvent<HTMLDivElement>) {
    // Clicar num cartão seleciona; só o fundo arrasta o quadro.
    if ((evento.target as HTMLElement).closest("[data-no]")) return;
    if ((evento.target as HTMLElement).closest("[data-controles]")) return;
    arrasto.current = { x: evento.clientX, y: evento.clientY };
    evento.currentTarget.setPointerCapture(evento.pointerId);
  }

  function aoMover(evento: PointerEvent<HTMLDivElement>) {
    const origem = arrasto.current;
    if (!origem) return;
    arrasto.current = { x: evento.clientX, y: evento.clientY };
    mudar({
      ...vista,
      x: vista.x + evento.clientX - origem.x,
      y: vista.y + evento.clientY - origem.y,
    });
  }

  function aoTeclar(evento: KeyboardEvent<HTMLDivElement>) {
    // Teclas dentro de um cartão ou controle (Enter, Tab…) são deles; só o próprio quadro as usa.
    if (evento.target !== evento.currentTarget) return;
    const deslocamento: Record<string, [number, number]> = {
      ArrowLeft: [PASSO_DO_TECLADO, 0],
      ArrowRight: [-PASSO_DO_TECLADO, 0],
      ArrowUp: [0, PASSO_DO_TECLADO],
      ArrowDown: [0, -PASSO_DO_TECLADO],
    };
    const mover = deslocamento[evento.key];
    if (mover) {
      evento.preventDefault();
      mudar({ ...vista, x: vista.x + mover[0], y: vista.y + mover[1] });
    } else if (evento.key === "+" || evento.key === "=") {
      mudar(zoomEm(vista, centro, PASSO_DO_ZOOM));
    } else if (evento.key === "-") {
      mudar(zoomEm(vista, centro, 1 / PASSO_DO_ZOOM));
    } else if (evento.key === "0") {
      setManual(null);
    }
  }

  const grade = 24 * vista.escala;
  return (
    <div
      ref={area}
      role="group"
      aria-label={rotulo}
      aria-describedby="ajuda-do-mapa"
      tabIndex={0}
      onPointerDown={aoPressionar}
      onPointerMove={aoMover}
      onPointerUp={() => (arrasto.current = null)}
      onPointerCancel={() => (arrasto.current = null)}
      onKeyDown={aoTeclar}
      className="relative h-[min(42rem,calc(100vh-17rem))] min-h-[24rem] cursor-grab touch-none overflow-hidden rounded-cartao border border-pedra-300 bg-superficie active:cursor-grabbing"
      style={{
        backgroundImage: "radial-gradient(circle, var(--color-pedra-300) 1.1px, transparent 1.3px)",
        backgroundSize: `${grade}px ${grade}px`,
        backgroundPosition: `${vista.x}px ${vista.y}px`,
      }}
    >
      <div
        className="absolute top-0 left-0 origin-top-left"
        style={{
          width: conteudo.largura,
          height: conteudo.altura,
          transform: `translate(${vista.x}px, ${vista.y}px) scale(${vista.escala})`,
        }}
      >
        {children}
      </div>

      <div
        data-controles
        className="absolute bottom-3 left-3 flex items-center gap-1 rounded-controle border border-pedra-300 bg-superficie p-1 shadow-cartao"
      >
        <Botao
          variante="fantasma"
          tamanho="pequeno"
          aria-label="Diminuir o zoom"
          onClick={() => mudar(zoomEm(vista, centro, 1 / PASSO_DO_ZOOM))}
        >
          <Icone nome="menos" />
        </Botao>
        <span className="w-11 text-center font-mono text-xs text-pedra-600 tabular-nums">
          {Math.round(vista.escala * 100)}%
        </span>
        <Botao
          variante="fantasma"
          tamanho="pequeno"
          aria-label="Aumentar o zoom"
          onClick={() => mudar(zoomEm(vista, centro, PASSO_DO_ZOOM))}
        >
          <Icone nome="mais" />
        </Botao>
        <Botao
          variante="fantasma"
          tamanho="pequeno"
          aria-label="Ajustar à tela"
          title="Ajustar à tela"
          onClick={() => setManual(null)}
        >
          <Icone nome="ajustar" />
        </Botao>
      </div>
      <p id="ajuda-do-mapa" className="sr-only">
        Arraste o fundo para mover. Ctrl ou Command com a roda dá zoom. Com o foco aqui, use as
        setas para mover, mais e menos para o zoom e zero para ajustar à tela.
      </p>
    </div>
  );
}
