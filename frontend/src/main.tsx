import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Autenticacao } from "./auth/Autenticacao";
import { TelaDeCarregamento } from "./auth/telas";
import { carregarConfig, type ConfigDoApp } from "./config";
import "./index.css";

const raiz = document.getElementById("raiz");
if (!raiz) {
  throw new Error("Elemento #raiz não encontrado em index.html.");
}
const arvore = createRoot(raiz);
arvore.render(<TelaDeCarregamento />);

carregarConfig().then(
  (config: ConfigDoApp) =>
    arvore.render(
      <StrictMode>
        <Autenticacao config={config}>
          <App />
        </Autenticacao>
      </StrictMode>,
    ),
  (erro: unknown) =>
    arvore.render(
      <main className="mx-auto max-w-md px-4 py-8">
        <p role="alert">{erro instanceof Error ? erro.message : "Falha ao iniciar o app."}</p>
      </main>,
    ),
);

// O service worker guarda só arquivos estáticos (ver public/sw.js); em desenvolvimento ele atrapalharia o HMR.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined); // instalar o PWA é opcional
  });
}
