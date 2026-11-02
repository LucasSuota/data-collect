/**
 * Processo principal do Electron (AGENTS.md §4.1 e §12).
 *
 * Gera o token, inicia o backend Python como processo filho, lê a porta da primeira linha da
 * saída dele e abre a janela em `http://127.0.0.1:<porta>`. Se o backend cair, mostra um erro
 * em português em vez de uma janela em branco. Ao fechar, encerra o backend.
 *
 * A lógica testável está em `logica.ts`; este arquivo é a cola com o Electron e é verificado à mão.
 */
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import readline from "node:readline";
import { app, BrowserWindow, session } from "electron";
import {
  argumentoDoToken,
  comandoDoBackend,
  gerarToken,
  lerPortaDaPrimeiraLinha,
  mensagemDeFalhaDoBackend,
  paginaDeErro,
  politicaDeSeguranca,
  urlPermitida,
  type FalhaDoBackend,
} from "./logica";

const TEMPO_MAXIMO_PARA_INICIAR_MS = 30_000;
const TEMPO_PARA_FORCAR_O_ENCERRAMENTO_MS = 3_000;

let backend: ChildProcess | null = null;
let janela: BrowserWindow | null = null;
let encerrando = false;

if (!app.requestSingleInstanceLock()) {
  // Duas instâncias abririam dois backends sobre o mesmo banco SQLite.
  app.quit();
} else {
  app.on("second-instance", () => {
    if (janela?.isMinimized()) janela.restore();
    janela?.focus();
  });
  app.whenReady().then(iniciar);
  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", encerrarBackend);
}

async function iniciar(): Promise<void> {
  const token = gerarToken();
  negarPermissoes();

  let porta: number;
  try {
    porta = await iniciarBackend(token);
  } catch (falha) {
    abrirJanela(token, null).then((j) =>
      j.loadURL(paginaDeErro(mensagemDeFalhaDoBackend(falha as FalhaDoBackend))),
    );
    return;
  }

  definirPoliticaDeSeguranca(porta);
  const j = await abrirJanela(token, porta);
  void j.loadURL(`http://127.0.0.1:${porta}`);

  // Se o backend cair depois de aberto, a janela passa a explicar em vez de falhar calada.
  backend?.once("exit", (codigo) => {
    if (!encerrando) {
      void j.loadURL(paginaDeErro(mensagemDeFalhaDoBackend({ tipo: "encerrou", codigo })));
    }
  });
}

function iniciarBackend(token: string): Promise<number> {
  const comando = comandoDoBackend({
    empacotado: app.isPackaged,
    pastaDeRecursos: process.resourcesPath,
    plataforma: process.platform,
    raizDoRepositorio: path.resolve(__dirname, "..", ".."),
  });

  return new Promise<number>((resolve, reject: (falha: FalhaDoBackend) => void) => {
    const filho = spawn(comando.comando, comando.argumentos, {
      cwd: comando.cwd,
      env: { ...process.env, FORMS_TOKEN: token },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    backend = filho;

    let resolvido = false;
    const temporizador = setTimeout(
      () => falhar({ tipo: "nao-iniciou" }),
      TEMPO_MAXIMO_PARA_INICIAR_MS,
    );
    function falhar(falha: FalhaDoBackend) {
      if (resolvido) return;
      resolvido = true;
      clearTimeout(temporizador);
      reject(falha);
    }

    filho.once("error", () => falhar({ tipo: "nao-iniciou" }));
    filho.once("exit", (codigo) => falhar({ tipo: "encerrou", codigo }));
    filho.stderr.on("data", (dados: Buffer) => process.stderr.write(dados));

    // A primeira linha da saída é a porta; depois dela, o fluxo continua sendo drenado.
    const linhas = readline.createInterface({ input: filho.stdout });
    linhas.once("line", (linha) => {
      const porta = lerPortaDaPrimeiraLinha(linha);
      if (porta === null) return falhar({ tipo: "porta-invalida" });
      resolvido = true;
      clearTimeout(temporizador);
      resolve(porta);
    });
  });
}

async function abrirJanela(token: string, porta: number | null): Promise<BrowserWindow> {
  const nova = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    webPreferences: {
      contextIsolation: true, // a página não enxerga o Electron
      nodeIntegration: false, // nem o Node
      sandbox: true,
      webSecurity: true,
      devTools: !app.isPackaged,
      preload: path.join(__dirname, "preload.js"),
      additionalArguments: [argumentoDoToken(token)],
    },
  });
  janela = nova;
  nova.once("ready-to-show", () => nova.show());

  if (porta !== null) {
    const bloquear = (evento: Electron.Event, url: string) => {
      if (!urlPermitida(url, porta)) evento.preventDefault();
    };
    nova.webContents.on("will-navigate", bloquear);
    nova.webContents.on("will-redirect", bloquear);
  }
  // Nenhuma janela nova: link externo nem abre.
  nova.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  nova.on("closed", () => {
    janela = null;
  });
  return nova;
}

function negarPermissoes(): void {
  // Câmera, microfone, localização etc. nunca são pedidos pelo app (a foto usa o seletor de arquivo).
  session.defaultSession.setPermissionRequestHandler((_conteudo, _permissao, responder) =>
    responder(false),
  );
}

function definirPoliticaDeSeguranca(porta: number): void {
  const politica = politicaDeSeguranca(porta);
  session.defaultSession.webRequest.onHeadersReceived((detalhes, responder) => {
    responder({
      responseHeaders: {
        ...detalhes.responseHeaders,
        "Content-Security-Policy": [politica],
      },
    });
  });
}

function encerrarBackend(): void {
  encerrando = true;
  const filho = backend;
  if (!filho || filho.exitCode !== null || filho.pid === undefined) return;
  if (process.platform === "win32") {
    // No Windows `kill` não derruba os netos; `taskkill /t` derruba a árvore.
    spawn("taskkill", ["/pid", String(filho.pid), "/t", "/f"], {
      windowsHide: true,
    });
    return;
  }
  filho.kill("SIGTERM");
  setTimeout(() => filho.kill("SIGKILL"), TEMPO_PARA_FORCAR_O_ENCERRAMENTO_MS).unref();
}
