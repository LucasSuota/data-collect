/**
 * Preload: a única ponte entre a página e o Electron. Expõe SÓ o token da execução (§4.1).
 *
 * Roda com `sandbox` ligado, e um preload sandboxed não pode importar módulos locais; por isso
 * a leitura do argumento é repetida aqui (3 linhas) em vez de vir de `logica.ts`. Um teste
 * confere que o prefixo é o mesmo.
 */
import { contextBridge } from "electron";

const PREFIXO = "--forms-token=";

const argumento = process.argv.find((a) => a.startsWith(PREFIXO));
const token = argumento ? argumento.slice(PREFIXO.length) : "";

// Sem `urlBase`: no app instalado o front é servido pelo próprio backend (mesma origem).
contextBridge.exposeInMainWorld("formsApi", { token });
