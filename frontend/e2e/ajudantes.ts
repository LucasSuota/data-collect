import { execFileSync } from "node:child_process";
import type { Page } from "@playwright/test";

const MAILPIT = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";

/** O link do convite do primeiro administrador, que a API escreve no log na primeira subida. */
export function linkDoPrimeiroConvite(): string {
  if (process.env.E2E_INVITE_URL) return process.env.E2E_INVITE_URL;
  const log = execFileSync("docker", ["compose", "logs", "api", "--no-log-prefix"], {
    cwd: "..",
    encoding: "utf8",
    env: process.env,
  });
  const achado = [...log.matchAll(/\/convite\/([A-Za-z0-9_-]+)/g)].at(-1);
  if (!achado) throw new Error("O log da API não tem o link do convite (a equipe já foi criada?).");
  return `/convite/${achado[1]}`;
}

/** O código de verificação mais recente que o Logto enviou para o e-mail (caixa de teste, Mailpit). */
export async function codigoDeVerificacao(email: string): Promise<string> {
  for (let tentativa = 0; tentativa < 30; tentativa++) {
    const resposta = await fetch(
      `${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${email}`)}`,
    );
    const { messages } = (await resposta.json()) as { messages: { ID: string }[] };
    const id = messages[0]?.ID;
    if (id) {
      const mensagem = (await (await fetch(`${MAILPIT}/api/v1/message/${id}`)).json()) as {
        Text: string;
      };
      const codigo = /\b(\d{6})\b/.exec(mensagem.Text)?.[1];
      if (codigo) return codigo;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Nenhum código de verificação chegou para ${email}.`);
}

export async function esvaziarCaixa(): Promise<void> {
  await fetch(`${MAILPIT}/api/v1/messages`, { method: "DELETE" });
}

export async function paginaDeLogto(page: Page) {
  await page.waitForURL(/auth\.localhost/);
}

export const EMAIL = process.env.E2E_EMAIL ?? "admin@exemplo.com";
export const SENHA = process.env.E2E_SENHA ?? "Senha-de-teste-123";

async function naPaginaDeLogto(page: Page) {
  await page.waitForURL(/auth\.localhost/);
  await page.waitForLoadState("networkidle");
}

/** Cadastro pelo link do convite: e-mail, código recebido no Mailpit e senha. */
export async function criarContaPeloConvite(page: Page, link: string): Promise<void> {
  await esvaziarCaixa();
  await page.goto(link);
  await page.getByRole("button", { name: "Criar minha conta" }).click();
  await naPaginaDeLogto(page);
  await page.getByRole("textbox").first().fill(EMAIL);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Criar conta" }).click();
  const codigo = await codigoDeVerificacao(EMAIL);
  await page.locator("input").first().click();
  await page.keyboard.type(codigo);
  await page.waitForURL(/continue\/password/);
  await page.locator('input[type="password"]').fill(SENHA);
  await page.getByRole("button", { name: "Salvar senha" }).click();
}

/** Entra com e-mail e senha de uma conta que já existe. */
export async function entrarComSenha(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByRole("button", { name: "Entrar com e-mail e senha" }).click();
  await naPaginaDeLogto(page);
  await page.getByRole("textbox").first().fill(EMAIL);
  await page.locator('input[type="password"]').fill(SENHA);
  await page.getByRole("button", { name: /^Entrar$/ }).click();
}

/** Espera a tela de aceite ou o início, o que vier primeiro, e aceita os Termos se for o caso. */
export async function aceitarTermosSeFor(page: Page): Promise<void> {
  const titulo = page.getByRole("heading", { name: /^(Antes de continuar|Olá, )/ }).first();
  await titulo.waitFor({ timeout: 30_000 });
  if ((await titulo.innerText()).startsWith("Antes de continuar")) {
    await page.getByRole("checkbox", { name: /Li e aceito/ }).check();
    await page.getByRole("button", { name: "Continuar" }).click();
  }
}
