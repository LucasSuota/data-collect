import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  ESTADO_DA_SESSAO,
  aceitarTermosSeFor,
  criarContaPeloConvite,
  linkDoPrimeiroConvite,
  sessaoGuardada,
} from "./ajudantes";

/**
 * O caminho de quem recebe o convite: cria a conta no Logto, aceita os termos e chega ao início
 * da equipe. Roda só no celular (o convite é de uso único); o resto dos testes entra com senha.
 */
test.describe("primeiro acesso", () => {
  test("convite, cadastro, aceite dos termos e início da equipe", async ({ page }, info) => {
    test.skip(info.project.name !== "celular", "o convite é de uso único");
    test.skip(
      sessaoGuardada() !== undefined && !process.env.E2E_REFAZER,
      "a conta de teste já existe: para refazer o cadastro, apague frontend/.auth e suba a pilha do zero",
    );
    await criarContaPeloConvite(page, linkDoPrimeiroConvite());
    await aceitarTermosSeFor(page);

    await expect(page.getByRole("heading", { name: /^Olá, / })).toBeVisible();
    // Passeio do primeiro acesso: aparece e pode ser pulado.
    await page.getByRole("button", { name: "Pular passeio" }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByText("Administrador").locator("visible=true").first()).toBeVisible();

    // Os outros testes reaproveitam esta sessão em vez de entrar de novo a cada um.
    await page.context().storageState({ path: ESTADO_DA_SESSAO });

    const acessibilidade = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(acessibilidade.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
