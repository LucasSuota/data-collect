import { defineConfig, devices } from "@playwright/test";

/**
 * Ponta a ponta contra o stack REAL: API, Logto e Mailpit no `docker compose up` e o front no Vite
 * (AGENTS.md §8). Dois projetos, celular e desktop. Tudo em HTTP no localhost, sem certificado.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  // O front sobe sozinho; se já houver um `npm run dev` na porta 5173, é reaproveitado.
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "celular", use: { ...devices["Pixel 7"] } },
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
});
