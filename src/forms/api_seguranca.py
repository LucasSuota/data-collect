"""Defesas da API contra abuso e erro de uso (AGENTS.md §12).

- **Corpo limitado** (1 MB): um JSON maior que isso nunca é lido inteiro (413).
- **Cabeçalhos de segurança** em toda resposta.
- **Limite de taxa** por pessoa nas rotas caras (429 com `Retry-After`). É por processo: com mais
  de uma instância cada uma conta sozinha, e o limite global é do proxy (§4.1).

DDoS volumétrico não é coberto aqui nem em lugar nenhum do app (sem serviço de borda, §2.9).
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LIMITE_DO_CORPO_EM_BYTES = 1024 * 1024

CABECALHOS_DE_SEGURANCA = {
    b"x-content-type-options": b"nosniff",
    b"referrer-policy": b"no-referrer",
    b"x-frame-options": b"DENY",
    # Só a geolocalização fica liberada (campo `localizacao`); câmera e microfone, não.
    b"permissions-policy": b"geolocation=(self), camera=(), microphone=()",
    # A API só devolve JSON, CSV e texto: nada de página, script ou frame.
    b"content-security-policy": b"default-src 'none'; frame-ancestors 'none'",
}


class LimitarCorpo:
    """Middleware ASGI: recusa pelo `Content-Length` e, sem ele (chunked), lê no máximo `limite`
    bytes antes de recusar. O corpo lido é repassado ao app (no máximo 1 MB na memória)."""

    def __init__(self, app: ASGIApp, limite: int = LIMITE_DO_CORPO_EM_BYTES) -> None:
        self.app = app
        self.limite = limite

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declarado = dict(scope["headers"]).get(b"content-length")
        if declarado is not None and declarado.isdigit() and int(declarado) > self.limite:
            await self._recusar(scope, receive, send)
            return

        lidas: list[Message] = []
        total = 0
        while True:
            mensagem = await receive()
            if mensagem["type"] != "http.request":
                break  # o cliente desistiu
            lidas.append(mensagem)
            total += len(mensagem.get("body", b""))
            if total > self.limite:
                await self._recusar(scope, receive, send)
                return
            if not mensagem.get("more_body", False):
                break

        pendentes = iter(lidas)

        async def repassar() -> Message:
            return next(pendentes, None) or await receive()

        await self.app(scope, repassar, send)

    @staticmethod
    async def _recusar(scope: Scope, receive: Receive, send: Send) -> None:
        resposta = JSONResponse(
            status_code=413,
            content={"detalhe": "Requisição grande demais (máximo de 1 MB).", "erros": []},
        )
        await resposta(scope, receive, send)


class AcrescentarCabecalhosDeSeguranca:
    """Middleware ASGI: acrescenta os cabeçalhos a toda resposta da API."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def enviando(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                cabecalhos = list(mensagem.get("headers", []))
                existentes = {nome.lower() for nome, _ in cabecalhos}
                cabecalhos += [
                    (n, v) for n, v in CABECALHOS_DE_SEGURANCA.items() if n not in existentes
                ]
                if b"cache-control" not in existentes:
                    # Dado da equipe nunca fica em cache do navegador nem de intermediário.
                    cabecalhos.append((b"cache-control", b"no-store"))
                mensagem["headers"] = cabecalhos
            await send(mensagem)

        await self.app(scope, receive, enviando)


# --- limite de taxa ---


@dataclass(frozen=True)
class Limite:
    """No máximo `capacidade` pedidos por `janela_em_segundos`."""

    capacidade: int
    janela_em_segundos: float


class LimitadorDeTaxa:
    """Balde de fichas por chave: `capacidade` fichas que se repõem em `janela` segundos.

    Simples de explicar: cada pedido gasta uma ficha; sem ficha, espera `retry_after`. O relógio
    entra por parâmetro (§9.9) para o teste não depender do tempo real.
    """

    def __init__(self, relogio: Callable[[], float] = time.monotonic) -> None:
        self._relogio = relogio
        self._baldes: dict[tuple[str, str], tuple[float, float]] = {}
        self._trava = threading.Lock()

    def tentar(self, chave: tuple[str, str], limite: Limite) -> float | None:
        """`None` se passou; senão, quantos segundos esperar até a próxima ficha."""
        agora = self._relogio()
        taxa = limite.capacidade / limite.janela_em_segundos
        with self._trava:
            fichas, visto = self._baldes.get(chave, (float(limite.capacidade), agora))
            fichas = min(float(limite.capacidade), fichas + (agora - visto) * taxa)
            if fichas >= 1:
                self._baldes[chave] = (fichas - 1, agora)
                self._limpar(agora, limite.janela_em_segundos)
                return None
            self._baldes[chave] = (fichas, agora)
            return (1 - fichas) / taxa

    def _limpar(self, agora: float, janela: float) -> None:
        # Evita crescer sem fim: balde parado há mais que uma janela já está cheio de novo.
        if len(self._baldes) > 10_000:
            self._baldes = {k: v for k, v in self._baldes.items() if agora - v[1] < janela}


# Rotas caras (§12). Pedidos por janela, por pessoa. Valor generoso para uso normal.
LIMITES_POR_ROTA: dict[tuple[str, str], Limite] = {
    ("POST", "/definicoes/previa"): Limite(120, 60),
    ("GET", "/formularios/{formulario_id}/registros/exportar"): Limite(10, 60),
    ("GET", "/eu/exportar"): Limite(5, 60),
    ("GET", "/busca"): Limite(60, 60),
    ("POST", "/convites"): Limite(20, 3600),
    ("POST", "/templates/importar"): Limite(10, 60),
    ("POST", "/definicoes/gerar"): Limite(20, 60),
    ("POST", "/formularios/{formulario_id}/resumo"): Limite(20, 60),
    ("POST", "/assistente/perguntar"): Limite(30, 60),
    ("POST", "/chat"): Limite(30, 60),
}
