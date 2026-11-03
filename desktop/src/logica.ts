/**
 * Lógica pura do desktop (sem Electron): é o que dá para testar automaticamente. Janela,
 * processo filho e preload ficam em `principal.ts` e `preload.ts` e são verificados à mão.
 */
import { randomBytes } from "node:crypto";
import path from "node:path";

const ENDERECO_LOCAL = "127.0.0.1";
const PREFIXO_DO_ARGUMENTO_DO_TOKEN = "--forms-token=";

/** Lê `{"porta": N}`, a primeira linha da saída do backend (AGENTS.md §4.1). */
export function lerPortaDaPrimeiraLinha(linha: string): number | null {
  let lido: unknown;
  try {
    lido = JSON.parse(linha);
  } catch {
    return null;
  }
  if (typeof lido !== "object" || lido === null || !("porta" in lido)) return null;
  const { porta } = lido as { porta: unknown };
  return typeof porta === "number" && Number.isInteger(porta) && porta >= 1 && porta <= 65535
    ? porta
    : null;
}

export function origemDoBackend(porta: number): string {
  return `http://${ENDERECO_LOCAL}:${porta}`;
}

/**
 * A janela só navega para o backend local. Compara a ORIGEM já interpretada (não o início do
 * texto): `http://127.0.0.1:1234@evil.example` e `http://127.0.0.1:1234.evil.example` não passam.
 */
export function urlPermitida(url: string, porta: number): boolean {
  try {
    return new URL(url).origin === origemDoBackend(porta);
  } catch {
    return false;
  }
}

/** O token por execução (§4.1): gerado a cada início do app, nunca fixo nem gravado. */
export function gerarToken(): string {
  return randomBytes(32).toString("hex");
}

export function argumentoDoToken(token: string): string {
  return `${PREFIXO_DO_ARGUMENTO_DO_TOKEN}${token}`;
}

export function lerTokenDosArgumentos(argv: readonly string[]): string | null {
  const argumento = argv.find((a) => a.startsWith(PREFIXO_DO_ARGUMENTO_DO_TOKEN));
  const token = argumento?.slice(PREFIXO_DO_ARGUMENTO_DO_TOKEN.length);
  return token ? token : null;
}

export interface OpcoesDoBackend {
  empacotado: boolean;
  /** `process.resourcesPath` no app empacotado. */
  pastaDeRecursos: string;
  plataforma: NodeJS.Platform;
  raizDoRepositorio: string;
}

export interface ComandoDoBackend {
  comando: string;
  argumentos: string[];
  cwd?: string;
}

/** Empacotado: o executável do PyInstaller. Em desenvolvimento: o módulo Python pelo `uv`. */
export function comandoDoBackend(opcoes: OpcoesDoBackend): ComandoDoBackend {
  if (!opcoes.empacotado) {
    return {
      comando: "uv",
      argumentos: ["run", "python", "-m", "forms.app"],
      cwd: opcoes.raizDoRepositorio,
    };
  }
  const nome = opcoes.plataforma === "win32" ? "forms-backend.exe" : "forms-backend";
  // `path.posix`/`path.win32` conforme a plataforma alvo, para o teste valer em qualquer sistema.
  const juntar = opcoes.plataforma === "win32" ? path.win32.join : path.posix.join;
  return {
    comando: juntar(opcoes.pastaDeRecursos, "backend", nome),
    argumentos: [],
  };
}

export type FalhaDoBackend =
  | { tipo: "nao-iniciou" }
  | { tipo: "porta-invalida" }
  | { tipo: "encerrou"; codigo: number | null };

export function mensagemDeFalhaDoBackend(falha: FalhaDoBackend): string {
  switch (falha.tipo) {
    case "nao-iniciou":
      return "O servidor do aplicativo não conseguiu iniciar.";
    case "porta-invalida":
      return "O servidor do aplicativo não informou a porta de conexão.";
    case "encerrou":
      return falha.codigo === null
        ? "O servidor do aplicativo foi encerrado inesperadamente."
        : `O servidor do aplicativo foi encerrado inesperadamente (código ${falha.codigo}).`;
  }
}

/** Em vez de uma janela em branco, uma página clara em português (como data URL). */
export function paginaDeErro(mensagem: string): string {
  const html = `<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>data-collect</title>
<style>body{font-family:system-ui,sans-serif;margin:3rem auto;max-width:34rem;padding:0 1rem;color:#0f172a}
h1{font-size:1.4rem}p{line-height:1.5}.causa{background:#fef2f2;border:1px solid #fca5a5;border-radius:.5rem;padding:.75rem}</style>
</head>
<body>
<h1>Não foi possível abrir o aplicativo</h1>
<p class="causa">${escaparHtml(mensagem)}</p>
<p>Feche o aplicativo e abra de novo. Se o problema continuar, seus dados continuam guardados na pasta do aplicativo.</p>
</body>
</html>`;
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`;
}

/** CSP: tudo só da própria origem do backend; nada de script em linha, `eval`, objeto ou frame. */
export function politicaDeSeguranca(porta: number): string {
  void porta; // a origem é 'self'; a porta entra só se a política um dia precisar citá-la
  return [
    "default-src 'self'",
    "script-src 'self'",
    // O dnd-kit e o React escrevem `style` em linha.
    "style-src 'self' 'unsafe-inline'",
    // `blob:` para a miniatura de foto (o `<img>` não manda o token; a imagem vem por fetch).
    "img-src 'self' blob: data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

function escaparHtml(texto: string): string {
  return texto
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
