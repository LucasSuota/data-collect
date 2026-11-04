/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // A API libera CORS só para estas duas origens (AGENTS.md §4): a porta é fixa de propósito.
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Máquinas lentas (CI, notebook sob carga) estouravam os 5 s padrão no primeiro teste de cada arquivo.
    testTimeout: 20_000,
  },
});
