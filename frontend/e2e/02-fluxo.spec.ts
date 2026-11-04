import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { entrarSeNecessario, sessaoGuardada } from "./ajudantes";

/**
 * O trabalho do dia a dia, no celular e no desktop: entrar, importar um exemplo, preencher um
 * registro, ver o estado calculado pelo servidor, convidar alguém e passar pelas telas de gestão,
 * com verificação de acessibilidade e de desempenho.
 */

test.use({ storageState: sessaoGuardada() });

async function entrar(page: Page) {
  await entrarSeNecessario(page);
  await expect(page.getByRole("heading", { name: /^Olá, / })).toBeVisible();
  const passeio = page.getByRole("button", { name: "Pular passeio" });
  if (await passeio.isVisible().catch(() => false)) await passeio.click();
}

async function acessibilidade(page: Page) {
  const resultado = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(resultado.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`)).toEqual([]);
}

/** Vai por hash, que é como o app roteia. */
async function ir(page: Page, hash: string) {
  await page.evaluate((h) => (window.location.hash = h), hash);
}

test.describe("fluxo da equipe", () => {
  test("orçamento de desempenho: JS inicial pequeno e carga rápida", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const medidas = await page.evaluate(() => {
      const recursos = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
      const js = recursos
        .filter((r) => r.name.endsWith(".js"))
        .reduce((t, r) => t + r.transferSize, 0);
      const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming;
      return { js, domContentLoaded: nav.domContentLoadedEventEnd };
    });

    expect(medidas.js).toBeLessThan(200_000); // bytes transferidos (gzip), antes de qualquer tela pesada
    expect(medidas.domContentLoaded).toBeLessThan(4000);
  });

  test("importa um exemplo, preenche um registro e vê o estado calculado pelo servidor", async ({
    page,
  }) => {
    await entrar(page);

    // O exemplo pode já existir (outra execução ou outro viewport): só importa se faltar.
    await ir(page, "#/formularios");
    await expect(page.getByRole("heading", { name: "Formulários" })).toBeVisible();
    // Espera a lista assentar: o formulário ou o estado vazio, o que aparecer.
    await expect(
      page.getByText("corpo_de_prova").or(page.getByText("Nenhum formulário ainda")).first(),
    ).toBeVisible();
    const jaExiste = (await page.getByText("corpo_de_prova").count()) > 0;
    if (!jaExiste) {
      await ir(page, "#/exemplos");
      await page.getByRole("checkbox", { name: /corpo_de_prova|Corpo de prova/i }).check();
      await page.getByRole("button", { name: /^Importar/ }).click();
      await expect(page.getByRole("heading", { name: "Formulários" })).toBeVisible();
    }
    await expect(page.getByText("corpo_de_prova").first()).toBeVisible();
    await acessibilidade(page);

    await page
      .getByRole("button", { name: /Novo registro em/ })
      .first()
      .click();
    await page.getByLabel(/fck especificado/).fill("25");
    await page.getByLabel(/Diâmetro/).fill("100");
    await page.getByLabel(/Data de moldagem/).fill("2026-11-03");
    await page.getByLabel(/Carga de ruptura/).fill("246,6");
    // a prévia vem do servidor (31,4 MPa >= 25: conforme)
    await expect(page.getByText(/Conforme/).first()).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Salvar registro" }).click();

    await expect(page.getByRole("button", { name: /^Conformes · [1-9]\d*/ })).toBeVisible();
    await acessibilidade(page);
  });

  test("equipe: convida alguém e mostra o link uma vez", async ({ page }) => {
    await entrar(page);
    await ir(page, "#/equipe");
    await expect(page.getByRole("heading", { name: "Equipe" })).toBeVisible();
    await expect(page.getByText("(você)")).toBeVisible();

    await page.getByRole("button", { name: "Convidar" }).click();
    const convidada = `tecnico+${Date.now()}@exemplo.com`; // único por execução
    await page.getByLabel("E-mail").fill(convidada);
    await page.getByRole("button", { name: "Criar convite" }).click();
    await expect(page.getByLabel("Link do convite")).toHaveValue(/\/convite\//);
    await page.getByRole("button", { name: "Concluir" }).click();
    await page.getByRole("tab", { name: /^Convites · \d+/ }).click();
    await expect(page.getByText(convidada)).toBeVisible();
    await acessibilidade(page);
  });

  test("telas de gestão abrem e passam na verificação de acessibilidade", async ({ page }) => {
    await entrar(page);
    for (const [hash, titulo] of [
      ["#/cargos", "Cargos e permissões"],
      ["#/mapa", "Mapa de dependências"],
      ["#/ia", "Inteligência artificial"],
      ["#/ajuda", "Central de ajuda"],
      ["#/chat", "Assistente"],
    ] as const) {
      await ir(page, hash);
      await expect(page.getByRole("heading", { name: titulo }).first()).toBeVisible();
      await acessibilidade(page);
    }
  });
});
