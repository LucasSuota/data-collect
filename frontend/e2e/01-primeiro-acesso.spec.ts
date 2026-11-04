import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { aceitarTermosSeFor, criarContaPeloConvite, linkDoPrimeiroConvite } from "./ajudantes";

/**
 * O caminho de quem recebe o convite: cria a conta no Logto, aceita os termos e chega ao início
 * da equipe. Roda só no celular (o convite é de uso único); o resto dos testes entra com senha.
 */
test.describe("primeiro acesso", () => {
  test("convite, cadastro, aceite dos termos e início da equipe", async ({ page }, info) => {
    test.skip(info.project.name !== "celular", "o convite é de uso único");
    await criarContaPeloConvite(page, linkDoPrimeiroConvite());
    await aceitarTermosSeFor(page);

    await expect(page.getByRole("heading", { name: /^Olá, / })).toBeVisible();
    // Passeio do primeiro acesso: aparece e pode ser pulado.
    await page.getByRole("button", { name: "Pular passeio" }).click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(page.getByText("Administrador").first()).toBeVisible();

    const acessibilidade = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(acessibilidade.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
  });
});
