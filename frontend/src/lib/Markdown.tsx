import { Fragment, type ReactNode } from "react";

/**
 * Renderiza o Markdown dos guias e dos textos legais **sem HTML cru** (AGENTS.md §12): o texto vira
 * elementos React, que escapam tudo. Só entende o que os documentos do app usam: títulos, listas,
 * tabelas, citações, código, negrito, itálico e links. Um parser próprio e curto evita uma
 * dependência para um subconjunto tão pequeno, e é por isso que ele não tem como injetar HTML.
 */

const LINK_SEGURO = /^(https?:\/\/|mailto:|#\/)/i;
const ITEM_DE_LISTA = /^(\s*)([-*]|\d+\.)\s+(.*)$/;
const SEPARADOR_DE_TABELA = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

type Bloco =
  | { tipo: "titulo"; nivel: 1 | 2 | 3 | 4; texto: string }
  | { tipo: "paragrafo"; texto: string }
  | { tipo: "lista"; ordenada: boolean; itens: string[] }
  | { tipo: "citacao"; blocos: Bloco[] }
  | { tipo: "codigo"; texto: string }
  | { tipo: "tabela"; cabecalho: string[]; linhas: string[][] }
  | { tipo: "regua" };

export function lerBlocos(markdown: string): Bloco[] {
  const linhas = markdown
    .replace(/\r\n?/g, "\n")
    .replace(/^versao:.*\n/, "") // cabeçalho de versão dos textos legais
    .split("\n");
  const blocos: Bloco[] = [];
  let i = 0;
  while (i < linhas.length) {
    const linha = linhas[i] ?? "";
    if (linha.trim() === "") {
      i++;
    } else if (linha.trimStart().startsWith("```")) {
      const codigo: string[] = [];
      i++;
      while (i < linhas.length && !(linhas[i] ?? "").trimStart().startsWith("```")) {
        codigo.push(linhas[i] ?? "");
        i++;
      }
      i++; // a cerca de fechamento (ou o fim do texto)
      blocos.push({ tipo: "codigo", texto: codigo.join("\n") });
    } else if (/^#{1,4}\s/.test(linha)) {
      const marcas = linha.match(/^#+/)?.[0].length ?? 1;
      blocos.push({
        tipo: "titulo",
        nivel: Math.min(marcas, 4) as 1 | 2 | 3 | 4,
        texto: linha.replace(/^#+\s+/, "").trim(),
      });
      i++;
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(linha)) {
      blocos.push({ tipo: "regua" });
      i++;
    } else if (linha.startsWith(">")) {
      const citada: string[] = [];
      while (i < linhas.length && (linhas[i] ?? "").startsWith(">")) {
        citada.push((linhas[i] ?? "").replace(/^>\s?/, ""));
        i++;
      }
      blocos.push({ tipo: "citacao", blocos: lerBlocos(citada.join("\n")) });
    } else if (linha.includes("|") && SEPARADOR_DE_TABELA.test(linhas[i + 1] ?? "")) {
      const cabecalho = celulas(linha);
      i += 2;
      const corpo: string[][] = [];
      while (i < linhas.length && (linhas[i] ?? "").includes("|")) {
        corpo.push(celulas(linhas[i] ?? ""));
        i++;
      }
      blocos.push({ tipo: "tabela", cabecalho, linhas: corpo });
    } else if (ITEM_DE_LISTA.test(linha)) {
      const ordenada = /^\s*\d+\./.test(linha);
      const itens: string[] = [];
      while (i < linhas.length) {
        const atual = linhas[i] ?? "";
        const item = ITEM_DE_LISTA.exec(atual);
        if (item) {
          itens.push(item[3] ?? "");
        } else if (atual.trim() !== "" && /^\s{2,}\S/.test(atual) && itens.length > 0) {
          itens[itens.length - 1] += ` ${atual.trim()}`; // continuação do item
        } else {
          break;
        }
        i++;
      }
      blocos.push({ tipo: "lista", ordenada, itens });
    } else {
      const texto: string[] = [];
      while (i < linhas.length) {
        const atual = linhas[i] ?? "";
        if (atual.trim() === "" || /^(#{1,4}\s|>|```)/.test(atual) || ITEM_DE_LISTA.test(atual))
          break;
        texto.push(atual.trim());
        i++;
      }
      blocos.push({ tipo: "paragrafo", texto: texto.join(" ") });
    }
  }
  return blocos;
}

function celulas(linha: string): string[] {
  return linha
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(\[[^\]]+\]\([^)\s]+\))/;

function inline(texto: string, chave = "i"): ReactNode[] {
  const saida: ReactNode[] = [];
  let resto = texto;
  let n = 0;
  while (resto) {
    const achado = INLINE.exec(resto);
    if (!achado) {
      saida.push(resto);
      break;
    }
    if (achado.index > 0) saida.push(resto.slice(0, achado.index));
    const trecho = achado[0];
    const k = `${chave}-${n++}`;
    if (achado[1]) {
      saida.push(
        <code key={k} className="rounded-controle bg-pedra-100 px-1 py-0.5 font-mono text-[0.85em]">
          {trecho.slice(1, -1)}
        </code>,
      );
    } else if (achado[2]) {
      saida.push(<strong key={k}>{inline(trecho.slice(2, -2), k)}</strong>);
    } else if (achado[3]) {
      saida.push(<em key={k}>{inline(trecho.slice(1, -1), k)}</em>);
    } else {
      const partes = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(trecho);
      const rotulo = partes?.[1] ?? trecho;
      const destino = partes?.[2] ?? "";
      if (LINK_SEGURO.test(destino)) {
        const externo = !destino.startsWith("#/");
        saida.push(
          <a
            key={k}
            href={destino}
            className="text-sinal-500 underline underline-offset-2"
            {...(externo ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          >
            {rotulo}
          </a>,
        );
      } else {
        saida.push(rotulo); // esquema não permitido (javascript:, data:...): só o texto
      }
    }
    resto = resto.slice(achado.index + trecho.length);
  }
  return saida;
}

function Blocos({ blocos }: { blocos: Bloco[] }) {
  return (
    <>
      {blocos.map((bloco, indice) => {
        const k = `b${indice}`;
        switch (bloco.tipo) {
          case "titulo": {
            const Titulo = `h${Math.min(bloco.nivel + 1, 6)}` as "h2" | "h3" | "h4" | "h5";
            const estilo =
              bloco.nivel === 1
                ? "mt-2 text-2xl font-extrabold"
                : bloco.nivel === 2
                  ? "mt-6 text-lg font-bold"
                  : "mt-4 text-base font-semibold";
            return (
              <Titulo key={k} className={estilo}>
                {inline(bloco.texto, k)}
              </Titulo>
            );
          }
          case "paragrafo":
            return (
              <p key={k} className="leading-relaxed">
                {inline(bloco.texto, k)}
              </p>
            );
          case "lista": {
            const Lista = bloco.ordenada ? "ol" : "ul";
            return (
              <Lista
                key={k}
                className={`${bloco.ordenada ? "list-decimal" : "list-disc"} flex flex-col gap-1 pl-5`}
              >
                {bloco.itens.map((item, j) => (
                  <li key={j}>{inline(item, `${k}-${j}`)}</li>
                ))}
              </Lista>
            );
          }
          case "citacao":
            return (
              <blockquote
                key={k}
                className="flex flex-col gap-2 border-l-2 border-sinal-300 bg-sinal-100/50 px-3 py-2 text-pedra-700"
              >
                <Blocos blocos={bloco.blocos} />
              </blockquote>
            );
          case "codigo":
            return (
              <pre
                key={k}
                className="overflow-x-auto rounded-controle bg-pedra-900 p-3 font-mono text-sm text-superficie"
              >
                <code>{bloco.texto}</code>
              </pre>
            );
          case "tabela":
            return (
              <div key={k} className="overflow-x-auto">
                <table className="w-full border-collapse text-left text-sm">
                  <thead>
                    <tr>
                      {bloco.cabecalho.map((c, j) => (
                        <th key={j} className="border-b border-pedra-300 px-2 py-1.5 font-semibold">
                          {inline(c, `${k}-h${j}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {bloco.linhas.map((linha, j) => (
                      <tr key={j}>
                        {linha.map((c, m) => (
                          <td key={m} className="border-b border-pedra-200 px-2 py-1.5 align-top">
                            {inline(c, `${k}-${j}-${m}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "regua":
            return <hr key={k} className="border-pedra-200" />;
        }
      })}
    </>
  );
}

export function Markdown({ texto }: { texto: string }) {
  return (
    <div className="flex flex-col gap-3 text-[0.9375rem]">
      <Fragment>
        <Blocos blocos={lerBlocos(texto)} />
      </Fragment>
    </div>
  );
}
