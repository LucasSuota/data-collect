"""Fixtures da API compartilhadas pelos testes de `test_api*.py`."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forms.api import Configuracao, criar_app
from forms.api_rotas import obter_agora

TOKEN = "token-de-teste"
ORIGEM_PERMITIDA = "http://localhost:5173"
AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def configuracao(tmp_path: Path) -> Configuracao:
    return Configuracao(
        banco=tmp_path / "dados" / "forms.db",
        pasta_de_dados=tmp_path / "dados",
        token=TOKEN,
        dispensar_token=False,
        origens_cors=(ORIGEM_PERMITIDA, "http://127.0.0.1:5173"),
    )


@pytest.fixture
def app(configuracao: Configuracao):
    aplicacao = criar_app(configuracao)
    aplicacao.dependency_overrides[obter_agora] = lambda: AGORA  # relógio fixo
    return aplicacao


@pytest.fixture
def cliente(app) -> TestClient:
    """Cliente já autenticado: a maioria dos testes não é sobre o token."""
    return TestClient(app, headers={"X-Forms-Token": TOKEN})
