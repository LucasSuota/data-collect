import {
  comandoDoBackend,
  gerarToken,
  lerPortaDaPrimeiraLinha,
  lerTokenDosArgumentos,
  argumentoDoToken,
  mensagemDeFalhaDoBackend,
  origemDoBackend,
  paginaDeErro,
  politicaDeSeguranca,
  urlPermitida,
} from "./logica";

describe("lerPortaDaPrimeiraLinha", () => {
  it("lê a porta do JSON que o backend imprime", () => {
    expect(lerPortaDaPrimeiraLinha('{"porta": 51234}')).toBe(51234);
    expect(lerPortaDaPrimeiraLinha('{"porta":8000}\n')).toBe(8000);
  });

  it.each([
    "",
    "   ",
    "não é json",
    "{}",
    '{"porta": "8000"}',
    '{"porta": 0}',
    '{"porta": 70000}',
    '{"porta": 80.5}',
    '{"porta": -1}',
    "[8000]",
    "8000",
    "null",
    '{"outra": 1}',
  ])("recusa %j", (linha) => {
    expect(lerPortaDaPrimeiraLinha(linha)).toBeNull();
  });
});

describe("urlPermitida: a janela só navega para o backend local", () => {
  const porta = 51234;

  it.each([
    "http://127.0.0.1:51234",
    "http://127.0.0.1:51234/",
    "http://127.0.0.1:51234/#/formularios/1/registros",
    "http://127.0.0.1:51234/assets/index.js",
  ])("permite %s", (url) => {
    expect(urlPermitida(url, porta)).toBe(true);
  });

  it.each([
    "https://example.com",
    "http://localhost:51234", // outra origem para o navegador, mesmo apontando para a mesma máquina
    "http://127.0.0.1:8000",
    "http://127.0.0.1",
    "https://127.0.0.1:51234",
    "http://127.0.0.1:51234@evil.example/",
    "http://127.0.0.1:51234.evil.example/",
    "http://evil.example/http://127.0.0.1:51234",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "data:text/html,<script>1</script>",
    "about:blank",
    "ftp://127.0.0.1:51234",
    "//127.0.0.1:51234",
    "",
    "não é uma url",
  ])("bloqueia %s", (url) => {
    expect(urlPermitida(url, porta)).toBe(false);
  });

  it("a origem é montada só com 127.0.0.1", () => {
    expect(origemDoBackend(51234)).toBe("http://127.0.0.1:51234");
  });
});

describe("token por execução", () => {
  it("é longo, hexadecimal e diferente a cada execução", () => {
    const a = gerarToken();
    const b = gerarToken();

    expect(a).toMatch(/^[0-9a-f]{64}$/);
    expect(a).not.toBe(b);
  });

  it("passa do processo principal para o preload por um argumento", () => {
    const argumento = argumentoDoToken("abc123");

    expect(lerTokenDosArgumentos(["electron", "--flag", argumento, "--outra"])).toBe("abc123");
  });

  it.each([[[]], [["--outra"]], [["--forms-token="]]])(
    "sem token nos argumentos (%j) devolve null",
    (argv) => {
      expect(lerTokenDosArgumentos(argv)).toBeNull();
    },
  );
});

describe("comandoDoBackend", () => {
  it("empacotado, é o executável do PyInstaller dentro dos recursos do app", () => {
    const comando = comandoDoBackend({
      empacotado: true,
      pastaDeRecursos: "/app/Resources",
      plataforma: "darwin",
      raizDoRepositorio: "/repo",
    });

    expect(comando).toEqual({
      comando: "/app/Resources/backend/forms-backend",
      argumentos: [],
    });
  });

  it("no Windows o executável tem .exe", () => {
    const comando = comandoDoBackend({
      empacotado: true,
      pastaDeRecursos: "C:\\app\\resources",
      plataforma: "win32",
      raizDoRepositorio: "C:\\repo",
    });

    expect(comando.comando.endsWith("forms-backend.exe")).toBe(true);
  });

  it("em desenvolvimento, roda o módulo Python pelo uv, na raiz do repositório", () => {
    const comando = comandoDoBackend({
      empacotado: false,
      pastaDeRecursos: "/ignorado",
      plataforma: "linux",
      raizDoRepositorio: "/repo",
    });

    expect(comando).toEqual({
      comando: "uv",
      argumentos: ["run", "python", "-m", "forms.app"],
      cwd: "/repo",
    });
  });
});

describe("página de erro", () => {
  it("é uma página em português, como data URL", () => {
    const url = paginaDeErro("O servidor não iniciou.");
    const html = decodeURIComponent(url.replace("data:text/html;charset=utf-8,", ""));

    expect(url.startsWith("data:text/html;charset=utf-8,")).toBe(true);
    expect(html).toContain('lang="pt-BR"');
    expect(html).toContain("O servidor não iniciou.");
    expect(html).toContain("Feche o aplicativo e abra de novo");
  });

  it("escapa HTML da mensagem (a causa pode vir de fora)", () => {
    const html = decodeURIComponent(
      paginaDeErro("<img src=x onerror=alert(1)>").split(",").slice(1).join(","),
    );

    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
  });

  it("explica a falha do backend em português", () => {
    expect(mensagemDeFalhaDoBackend({ tipo: "nao-iniciou" })).toMatch(/não conseguiu iniciar/);
    expect(mensagemDeFalhaDoBackend({ tipo: "encerrou", codigo: 3 })).toMatch(
      /encerrado.*código 3/,
    );
    expect(mensagemDeFalhaDoBackend({ tipo: "encerrou", codigo: null })).toMatch(/encerrado/);
    expect(mensagemDeFalhaDoBackend({ tipo: "porta-invalida" })).toMatch(/porta/);
  });
});

describe("politicaDeSeguranca (CSP)", () => {
  const politica = politicaDeSeguranca(51234);

  it("só carrega recursos da própria origem do backend", () => {
    expect(politica).toContain("default-src 'self'");
    expect(politica).toContain("connect-src 'self'");
  });

  it("deixa a miniatura de foto (blob:) e o estilo em linha do dnd-kit funcionarem", () => {
    expect(politica).toContain("img-src 'self' blob: data:");
    expect(politica).toContain("style-src 'self' 'unsafe-inline'");
  });

  it("não libera script em linha nem eval, nem objetos, nem enquadramento", () => {
    expect(politica).toContain("script-src 'self'");
    expect(politica).not.toContain("unsafe-eval");
    expect(politica).not.toMatch(/script-src[^;]*unsafe-inline/);
    expect(politica).toContain("object-src 'none'");
    expect(politica).toContain("frame-ancestors 'none'");
  });
});
