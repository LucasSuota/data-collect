import { readFileSync } from "node:fs";
import path from "node:path";
import { argumentoDoToken, lerTokenDosArgumentos } from "./logica";

describe("preload (autocontido, por causa do sandbox)", () => {
  const fonte = readFileSync(path.join(__dirname, "preload.ts"), "utf-8");

  it("usa o mesmo prefixo de argumento que o processo principal envia", () => {
    const prefixo = argumentoDoToken("x").replace("x", "");

    expect(fonte).toContain(`"${prefixo}"`);
    expect(lerTokenDosArgumentos([argumentoDoToken("abc")])).toBe("abc");
  });

  it("expõe só o token, e nada mais, à página", () => {
    expect(fonte.match(/exposeInMainWorld/g)).toHaveLength(1);
    expect(fonte).toContain('exposeInMainWorld("formsApi", { token })');
  });

  it("não importa nada além do electron (um preload sandboxed não carrega módulos locais)", () => {
    const importacoes = [...fonte.matchAll(/^import .* from "(.+)";$/gm)].map((m) => m[1]);

    expect(importacoes).toEqual(["electron"]);
  });
});

describe("processo principal: regras de segurança do §4.1", () => {
  const fonte = readFileSync(path.join(__dirname, "principal.ts"), "utf-8");

  it("contextIsolation ligado, nodeIntegration desligado e sandbox", () => {
    expect(fonte).toMatch(/contextIsolation:\s*true/);
    expect(fonte).toMatch(/nodeIntegration:\s*false/);
    expect(fonte).toMatch(/sandbox:\s*true/);
  });

  it("não usa o módulo remote nem desliga a segurança web", () => {
    expect(fonte).not.toMatch(/enableRemoteModule|@electron\/remote/);
    expect(fonte).not.toMatch(/webSecurity:\s*false/);
    expect(fonte).not.toMatch(/allowRunningInsecureContent/);
  });

  it("bloqueia a navegação e as janelas novas", () => {
    expect(fonte).toContain('"will-navigate"');
    expect(fonte).toContain("urlPermitida");
    expect(fonte).toMatch(/setWindowOpenHandler\(\(\) => \(\{ action: "deny" \}\)\)/);
  });

  it("gera o token a cada execução e o passa ao backend por variável de ambiente", () => {
    expect(fonte).toContain("gerarToken()");
    expect(fonte).toContain("FORMS_TOKEN: token");
  });

  it("o backend ouve só em 127.0.0.1 (a janela abre exatamente esse endereço)", () => {
    expect(fonte).toContain("http://127.0.0.1:${porta}");
    expect(fonte).not.toMatch(/localhost|0\.0\.0\.0/);
  });
});
