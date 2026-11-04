"""Fixtures compartilhadas: Postgres real (§8), equipe de teste e a API com autenticação trocada.

O banco de teste é o do `docker compose` (porta 5433) ou o de `FORMS_TEST_DSN`. As migrações
rodam uma vez por sessão, em um banco limpo; cada teste termina com `TRUNCATE` de tudo.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import psycopg
import pytest

from forms import banco
from forms.banco import Conexao
from forms.models import Contexto
from forms.permissoes import PERMISSOES

DSN_DE_TESTE = os.environ.get(
    "FORMS_TEST_DSN", "postgresql://forms:forms@127.0.0.1:5433/forms_test"
)
AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
TODAS_AS_PERMISSOES = frozenset(p.id for p in PERMISSOES)


@pytest.fixture(scope="session")
def dsn() -> str:
    """Banco limpo e migrado, uma vez por sessão."""
    try:
        bruta = psycopg.connect(DSN_DE_TESTE, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as erro:  # pragma: no cover - ambiente sem Postgres
        pytest.exit(
            f"Sem Postgres de teste em {DSN_DE_TESTE}: `docker compose up -d postgres`.\n{erro}",
            returncode=2,
        )
    with bruta:
        bruta.execute("DROP SCHEMA public CASCADE")
        bruta.execute("CREATE SCHEMA public")
        bruta.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
    conexao = banco.abrir_conexao(DSN_DE_TESTE, migrar_esquema=True)
    conexao.close()
    return DSN_DE_TESTE


@pytest.fixture(autouse=True)
def _limpar_o_banco_depois(request: pytest.FixtureRequest) -> Iterator[None]:
    yield
    if "dsn" not in request.fixturenames:
        return  # o teste nem tocou no banco
    with psycopg.connect(request.getfixturevalue("dsn"), autocommit=True) as c:
        tabelas = [
            linha[0]
            for linha in c.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                " AND tablename <> 'esquema_versao'"
            )
        ]
        if tabelas:
            todas = ", ".join(f'"{t}"' for t in tabelas)
            c.execute(f"TRUNCATE {todas} RESTART IDENTITY CASCADE")  # noqa: S608


def criar_equipe(
    conexao: Conexao, nome: str = "Equipe de teste", permissoes: frozenset[str] | None = None
) -> Contexto:
    """Cria equipe e pessoa de teste e devolve o contexto (todas as permissões, por padrão)."""
    grupo = conexao.execute(
        "INSERT INTO grupos (nome, criado_em) VALUES (%s, %s) RETURNING id", (nome, AGORA)
    ).fetchone()
    usuario = conexao.execute(
        "INSERT INTO usuarios (logto_sub, nome, email, criado_em) VALUES (%s, %s, %s, %s)"
        " RETURNING id",
        (f"sub-{nome}", "Pessoa de Teste", f"{nome}@teste.example".replace(" ", "."), AGORA),
    ).fetchone()
    assert grupo is not None and usuario is not None
    return Contexto(grupo["id"], usuario["id"], permissoes or TODAS_AS_PERMISSOES)


@pytest.fixture
def conexao(dsn: str) -> Iterator[Conexao]:
    """Conexão com a equipe de teste já declarada (como a API faz a cada requisição)."""
    con = banco.abrir_conexao(dsn)
    con.definir_contexto(criar_equipe(con))
    yield con
    con.close()


@pytest.fixture
def outra_equipe(dsn: str) -> Iterator[Conexao]:
    """Conexão de uma segunda equipe, para provar o isolamento entre equipes (§2.13)."""
    con = banco.abrir_conexao(dsn)
    con.definir_contexto(criar_equipe(con, "Outra equipe"))
    yield con
    con.close()


# --- API: Logto de mentira (chaves geradas aqui) e equipe de teste com pessoa autenticada ---

import time  # noqa: E402

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from forms import servico_equipes  # noqa: E402
from forms.api import Configuracao, criar_app  # noqa: E402
from forms.api_dependencias import obter_agora  # noqa: E402
from forms.auth import ChaveFixa, ValidadorDeToken  # noqa: E402

EMISSOR = "https://logto.teste/oidc"
AUDIENCIA = "https://api.teste"
ORIGEM_PERMITIDA = "http://localhost:5173"


@pytest.fixture(scope="session")
def chave_privada() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP384R1())


def emitir_token(
    chave: ec.EllipticCurvePrivateKey,
    sub: str,
    *,
    expira_em: int = 600,
    audiencia: str = AUDIENCIA,
    emissor: str = EMISSOR,
    **extra: object,
) -> str:
    agora = int(time.time())
    declaracoes = {
        "sub": sub,
        "iss": emissor,
        "aud": audiencia,
        "iat": agora,
        "exp": agora + expira_em,
        **extra,
    }
    return jwt.encode(declaracoes, chave, algorithm="ES384")


@pytest.fixture
def validador(chave_privada: ec.EllipticCurvePrivateKey) -> ValidadorDeToken:
    return ValidadorDeToken(EMISSOR, AUDIENCIA, ChaveFixa(chave_privada.public_key()))


@pytest.fixture
def configuracao(dsn: str) -> Configuracao:
    return Configuracao(
        dsn=dsn,
        origens_cors=(ORIGEM_PERMITIDA, "http://127.0.0.1:5173"),
        logto_endpoint="https://logto.teste",
        logto_audiencia=AUDIENCIA,
    )


@pytest.fixture
def app(configuracao: Configuracao, validador: ValidadorDeToken, dsn: str):
    # Como em produção: a API roda no papel `forms_app`, sujeito ao Row Level Security.
    pool = banco.criar_pool(dsn, tamanho_maximo=4, papel="forms_app")
    aplicacao = criar_app(configuracao, pool=pool, validador=validador)
    aplicacao.dependency_overrides[obter_agora] = lambda: AGORA  # relógio fixo
    yield aplicacao
    pool.close()


def criar_pessoa_na_equipe(
    dsn: str, nome: str, cargo: str = "Administrador", grupo_id: int | None = None
) -> dict[str, int | str]:
    """Pessoa com termos aceitos, membro de uma equipe (nova, se `grupo_id` não vier)."""
    con = banco.abrir_conexao(dsn)
    try:
        if grupo_id is None:
            grupo, _ = servico_equipes.criar_equipe(con, f"Equipe de {nome}", AGORA)
            grupo_id = grupo.id
        con.definir_contexto(Contexto(grupo_id, None))
        cargo_id = next(c.id for c in servico_equipes.listar_cargos(con) if c.nome == cargo)
        con.definir_contexto(None)
        sub = f"sub-{nome}"
        usuario = servico_equipes.identificar(con, sub, nome, f"{nome}@teste.example", AGORA)
        servico_equipes.repositorio_equipes.adicionar_membro(
            con, grupo_id, usuario.id, cargo_id, AGORA
        )
        servico_equipes.aceitar_termos(con, usuario.id, AGORA)
        return {"grupo_id": grupo_id, "usuario_id": usuario.id, "sub": sub}
    finally:
        con.close()


def cliente_da_pessoa(app, chave, pessoa: dict) -> TestClient:
    return TestClient(
        app,
        headers={
            "Authorization": f"Bearer {emitir_token(chave, str(pessoa['sub']))}",
            "X-Equipe": str(pessoa["grupo_id"]),
        },
    )


@pytest.fixture
def pessoa(dsn: str) -> dict[str, int | str]:
    return criar_pessoa_na_equipe(dsn, "ana")


@pytest.fixture
def cliente(app, chave_privada, pessoa) -> TestClient:
    """Cliente já autenticado como administrador: a maioria dos testes não é sobre acesso."""
    return cliente_da_pessoa(app, chave_privada, pessoa)


@pytest.fixture
def emitir(chave_privada):
    """`emitir(sub, expira_em=..., audiencia=...)` -> JWT assinado pela chave de teste."""
    import functools

    return functools.partial(emitir_token, chave_privada)
