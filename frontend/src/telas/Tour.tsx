import { useState } from "react";
import { Botao, Gaveta } from "../ui";

const PASSOS = [
  {
    titulo: "Bem-vindo ao data-collect",
    texto:
      "Aqui sua equipe monta formulários, preenche registros e acompanha os resultados, tudo no mesmo lugar.",
  },
  {
    titulo: "Formulários",
    texto:
      "Um formulário é uma definição versionada: campos, cálculos e regras de conformidade. Mudar um formulário nunca quebra os registros antigos.",
  },
  {
    titulo: "Registros",
    texto:
      "Cada preenchimento é um registro. O servidor valida e recalcula tudo ao salvar, então o resultado é o mesmo para todo mundo.",
  },
  {
    titulo: "Vínculos entre formulários",
    texto:
      "Um formulário pode depender de outro (ensaio, proctor, in situ). O mapa de vínculos mostra quem aponta para quem.",
  },
  {
    titulo: "Ajuda sempre à mão",
    texto:
      "A Central de ajuda e o Assistente respondem dúvidas sobre o app. Você pode rever este passeio quando quiser, na Ajuda.",
  },
];

/** Passeio curto do primeiro acesso: pode ser pulado e revisto (AGENTS.md §2.16). */
export function Tour({
  passoInicial = 0,
  aoAvancar,
  aoTerminar,
}: {
  passoInicial?: number;
  aoAvancar: (passo: number) => void;
  aoTerminar: () => void;
}) {
  const [passo, setPasso] = useState(Math.min(passoInicial, PASSOS.length - 1));
  const atual = PASSOS[passo] ?? PASSOS[0]!;
  const ultimo = passo === PASSOS.length - 1;

  return (
    <Gaveta
      titulo={atual.titulo}
      subtitulo={`Passo ${passo + 1} de ${PASSOS.length}`}
      aoFechar={aoTerminar}
    >
      <div className="flex flex-1 flex-col gap-6 p-5">
        <p className="leading-relaxed">{atual.texto}</p>
        <div className="mt-auto flex flex-wrap items-center gap-2">
          <Botao variante="fantasma" onClick={aoTerminar}>
            Pular passeio
          </Botao>
          <div className="ml-auto flex gap-2">
            {passo > 0 ? <Botao onClick={() => setPasso(passo - 1)}>Voltar</Botao> : null}
            <Botao
              variante="primario"
              onClick={() => {
                if (ultimo) {
                  aoTerminar();
                } else {
                  setPasso(passo + 1);
                  aoAvancar(passo + 1);
                }
              }}
            >
              {ultimo ? "Concluir" : "Próximo"}
            </Botao>
          </div>
        </div>
      </div>
    </Gaveta>
  );
}
