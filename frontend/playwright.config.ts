import { defineConfig, devices } from "@playwright/test";

/**
 * Ponta a ponta contra o stack REAL (`docker compose up`): proxy, API, Logto e Mailpit
 * (AGENTS.md §8). Dois projetos, celular e desktop. O certificado do Caddy em `localhost` é de uma
 * CA interna, por isso `ignoreHTTPSErrors`.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "https://localhost",
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "celular", use: { ...devices["Pixel 7"] } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
  ],
});
