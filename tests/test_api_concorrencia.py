"""Requisições simultâneas: cada uma tem a sua conexão, mesmo quando a dependência e o endpoint
rodam em threads diferentes do pool (o que o `TestClient` sequencial nunca provoca)."""

import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

DEFINICAO = {"campos": [{"id": "obs", "tipo": "texto", "rotulo": "Observação"}]}
REQUISICOES_SIMULTANEAS = 60


async def _chamar_em_paralelo(
    app: FastAPI, caminhos: list[str], cabecalhos: dict[str, str]
) -> list[httpx.Response]:
    # `raise_app_exceptions=False`: falha do servidor vira resposta 500, e o teste a enxerga.
    transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transporte, base_url="http://testserver", headers=cabecalhos
    ) as cliente:
        return await asyncio.gather(*(cliente.get(caminho) for caminho in caminhos))


def test_requisicoes_simultaneas_nao_quebram_por_causa_da_thread_da_conexao(
    app: FastAPI, cliente: TestClient
):
    # Arrange
    criado = cliente.post("/formularios", json={"nome": "ensaio", "definicao": DEFINICAO})
    assert criado.status_code == 201, criado.text
    caminhos = ["/formularios", "/formularios/1", "/catalogo"] * (REQUISICOES_SIMULTANEAS // 3)

    # Act
    respostas = asyncio.run(_chamar_em_paralelo(app, caminhos, dict(cliente.headers)))

    # Assert
    status = [resposta.status_code for resposta in respostas]
    assert status == [200] * len(caminhos)
