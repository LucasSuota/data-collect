import { useCallback, useEffect, useState } from "react";

/**
 * Navegação por `#hash`, sem biblioteca de rotas: são poucas telas, e o backend serve só o
 * `index.html` (uma rota de caminho precisaria de fallback no servidor).
 */
export type Rota =
  | { nome: "formularios" }
  | { nome: "mapa" }
  | { nome: "registros"; formularioId: number }
  | { nome: "novoRegistro"; formularioId: number }
  | { nome: "registro"; registroId: number }
  | { nome: "novoFormulario"; pastaId?: number }
  | { nome: "pasta"; pastaId: number }
  | { nome: "criarComIa" }
  | { nome: "editarFormulario"; formularioId: number }
  | { nome: "naoEncontrada" };

const INTEIRO = /^[1-9]\d*$/;
const NAO_ENCONTRADA: Rota = { nome: "naoEncontrada" };

export function lerRota(hash: string): Rota {
  const caminho = hash.replace(/^#\/?/, "");
  if (caminho === "") return { nome: "formularios" };
  const partes = caminho.split("/");

  if (partes[0] === "mapa" && partes.length === 1) return { nome: "mapa" };
  if (partes[0] === "construtor" && partes.length === 1) return { nome: "novoFormulario" };
  if (partes[0] === "construtor" && partes.length === 3 && partes[1] === "pasta") {
    return ehId(partes[2])
      ? { nome: "novoFormulario", pastaId: Number(partes[2]) }
      : NAO_ENCONTRADA;
  }
  if (partes[0] === "pastas" && partes.length === 2 && ehId(partes[1])) {
    return { nome: "pasta", pastaId: Number(partes[1]) };
  }
  if (partes[0] === "construtor" && partes.length === 2 && partes[1] === "ia") {
    return { nome: "criarComIa" };
  }
  if (partes[0] === "registros" && partes.length === 2 && ehId(partes[1])) {
    return { nome: "registro", registroId: Number(partes[1]) };
  }
  if (partes[0] === "formularios" && partes.length === 3 && ehId(partes[1])) {
    const formularioId = Number(partes[1]);
    if (partes[2] === "registros") return { nome: "registros", formularioId };
    if (partes[2] === "novo") return { nome: "novoRegistro", formularioId };
    if (partes[2] === "editar") return { nome: "editarFormulario", formularioId };
  }
  return { nome: "naoEncontrada" };
}

export function caminhoDe(rota: Rota): string {
  switch (rota.nome) {
    case "formularios":
      return "#/";
    case "mapa":
      return "#/mapa";
    case "registros":
      return `#/formularios/${rota.formularioId}/registros`;
    case "novoRegistro":
      return `#/formularios/${rota.formularioId}/novo`;
    case "registro":
      return `#/registros/${rota.registroId}`;
    case "novoFormulario":
      return rota.pastaId === undefined ? "#/construtor" : `#/construtor/pasta/${rota.pastaId}`;
    case "pasta":
      return `#/pastas/${rota.pastaId}`;
    case "criarComIa":
      return "#/construtor/ia";
    case "editarFormulario":
      return `#/formularios/${rota.formularioId}/editar`;
    case "naoEncontrada":
      return "#/";
  }
}

export function useRota(): [Rota, (rota: Rota) => void] {
  const [rota, setRota] = useState(() => lerRota(window.location.hash));
  useEffect(() => {
    const aoMudar = () => setRota(lerRota(window.location.hash));
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);
  const navegar = useCallback((destino: Rota) => {
    window.location.hash = caminhoDe(destino);
  }, []);
  return [rota, navegar];
}

function ehId(texto: string | undefined): texto is string {
  return texto !== undefined && INTEIRO.test(texto);
}
