"""A API HTTP: monta o FastAPI, a autenticação, o CORS e o formato de erro uniforme.

Ponto de entrada: `uvicorn forms.api:app_do_ambiente --factory` (AGENTS.md §4.1). Pydantic e HTTP
só existem aqui e em `api_*.py`; toda regra de negócio fica em `servico*.py` e abaixo.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass
from datetime import UTC, datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from psycopg_pool import ConnectionPool
from starlette.exceptions import HTTPException as ExcecaoHttp

from forms import banco, servico_equipes
from forms.api_equipes import roteador as roteador_equipes
from forms.api_equipes import roteador_publico
from forms.api_esquemas import ErroDeCampoSaida
from forms.api_extensoes import Extensao, descobrir_extensoes, resposta_de_erro
from forms.api_permissoes import verificar_matriz
from forms.api_rotas import roteador
from forms.auth import ValidadorDeToken, validador_do_ambiente
from forms.models import (
    CargoInvalido,
    ConflitoDeRevisao,
    DefinicaoInvalida,
    ErroDeDominio,
    ExclusaoBloqueada,
    LoteInvalido,
    NaoAutenticado,
    NaoEncontrado,
    PastaInvalida,
    RegistroInvalido,
    SemAcessoAEquipe,
    SemPermissao,
    TermosPendentes,
    ValorInvalido,
)

ORIGENS_PADRAO = ("http://localhost:5173", "http://127.0.0.1:5173")
DSN_PADRAO = "postgresql://forms_app:forms_app@127.0.0.1:5433/forms"
CABECALHOS_PERMITIDOS = ["Authorization", "Content-Type", "X-Equipe", "If-Match"]


@dataclass(frozen=True)
class Configuracao:
    dsn: str
    origens_cors: tuple[str, ...]
    # Logto auto-hospedado (§2.12). Sem eles a API recusa todo pedido autenticado (falha fechada).
    logto_endpoint: str | None = None
    logto_audiencia: str | None = None
    # Quem migra o esquema (o dono do banco); vazio = não migra ao iniciar.
    dsn_de_migracao: str | None = None
    producao: bool = False
    primeiro_administrador: str | None = None
    nome_da_primeira_equipe: str = "Minha equipe"

    def __post_init__(self) -> None:
        if "*" in self.origens_cors:
            raise ValueError(
                "O CORS nunca pode liberar '*': liste as origens do front (AGENTS.md §12)."
            )

    @classmethod
    def do_ambiente(cls, ambiente: Mapping[str, str] | None = None) -> "Configuracao":
        """Lê `FORMS_DATABASE_URL`, `FORMS_MIGRATION_URL`, `FORMS_CORS_ORIGINS`, `LOGTO_ENDPOINT`,
        `LOGTO_API_RESOURCE`, `FORMS_AMBIENTE`, `FORMS_ADMIN_EMAIL` e `FORMS_EQUIPE_INICIAL`."""
        if ambiente is None:
            load_dotenv()  # o `.env` (fora do git) complementa o ambiente real
            ambiente = os.environ
        origens = tuple(
            o.strip() for o in (ambiente.get("FORMS_CORS_ORIGINS") or "").split(",") if o.strip()
        )
        return cls(
            dsn=ambiente.get("FORMS_DATABASE_URL") or DSN_PADRAO,
            origens_cors=origens or ORIGENS_PADRAO,
            logto_endpoint=ambiente.get("LOGTO_ENDPOINT") or None,
            logto_audiencia=ambiente.get("LOGTO_API_RESOURCE") or None,
            dsn_de_migracao=ambiente.get("FORMS_MIGRATION_URL") or None,
            producao=(ambiente.get("FORMS_AMBIENTE") or "").strip().lower() == "producao",
            primeiro_administrador=ambiente.get("FORMS_ADMIN_EMAIL") or None,
            nome_da_primeira_equipe=ambiente.get("FORMS_EQUIPE_INICIAL") or "Minha equipe",
        )


def criar_app(
    configuracao: Configuracao,
    extensoes: Sequence[Extensao] = (),
    pool: ConnectionPool[banco.Conexao] | None = None,
    validador: ValidadorDeToken | None = None,
) -> FastAPI:
    """Monta a aplicação. `pool` e `validador` podem ser injetados (testes); sem eles, saem da
    configuração. Sem Logto configurado, `validador` fica vazio e a API recusa todo pedido
    autenticado."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        if configuracao.dsn_de_migracao:
            with closing(banco.abrir_conexao(configuracao.dsn_de_migracao)) as conexao:
                banco.migrar(conexao)
        proprio = pool is None
        app.state.pool = (
            pool
            if pool is not None
            else banco.criar_pool(configuracao.dsn, tamanho_maximo=banco.TAMANHO_DO_POOL)
        )
        try:
            _bootstrap(app, configuracao)
            yield
        finally:
            if proprio:
                app.state.pool.close()

    documentacao = None if configuracao.producao else "/docs"
    app = FastAPI(
        title="data-collect",
        version="0.2.0",
        description=(
            "API do data-collect. Todo erro tem o formato `{detalhe, erros: [{campo, mensagem}]}`. "
            "Envie `Authorization: Bearer <token do Logto>` e, se estiver em mais de uma equipe, "
            "`X-Equipe: <id>`."
        ),
        lifespan=ciclo_de_vida,
        docs_url=documentacao,
        redoc_url=None,
        openapi_url=None if configuracao.producao else "/openapi.json",
    )
    app.state.configuracao = configuracao
    app.state.validador = validador or _validador_da_configuracao(configuracao)
    app.state.limite_do_pool = asyncio.Semaphore(_tamanho_do_pool(pool, configuracao))
    if pool is not None:
        app.state.pool = pool
    app.include_router(roteador_publico)
    app.include_router(roteador)
    app.include_router(roteador_equipes)
    for extensao in extensoes:
        app.include_router(extensao.roteador)
        for tipo, tratador in extensao.tratadores.items():
            app.add_exception_handler(tipo, tratador)
    verificar_matriz(app)  # rota sem decisão de permissão derruba a subida (falha fechada)
    _registrar_tratadores_de_erro(app)

    # Ordem importa: o último adicionado fica por fora. O CORS vai por fora de tudo, para o
    # preflight (OPTIONS, que não leva token) passar e o 401 também receber os cabeçalhos CORS.
    # O tratador de erro inesperado fica por dentro: o 500 precisa passar pelo CORS, senão o
    # navegador o esconde e o front acha que o servidor caiu.
    app.middleware("http")(_responder_erro_inesperado)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(configuracao.origens_cors),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=CABECALHOS_PERMITIDOS,
        expose_headers=["Content-Disposition", "ETag"],
        allow_credentials=False,
    )
    return app


def _tamanho_do_pool(pool: ConnectionPool[banco.Conexao] | None, configuracao: Configuracao) -> int:
    return pool.max_size if pool is not None else banco.TAMANHO_DO_POOL


def _validador_da_configuracao(configuracao: Configuracao) -> ValidadorDeToken | None:
    if configuracao.logto_endpoint and configuracao.logto_audiencia:
        return validador_do_ambiente(configuracao.logto_endpoint, configuracao.logto_audiencia)
    return None


def _bootstrap(app: FastAPI, configuracao: Configuracao) -> None:
    """Instalação vazia + `FORMS_ADMIN_EMAIL`: cria a equipe e o convite do primeiro
    administrador, e mostra o link uma única vez (o banco guarda só o hash, §12)."""
    if not configuracao.primeiro_administrador:
        return
    with app.state.pool.connection() as conexao:
        token = servico_equipes.garantir_primeiro_administrador(
            conexao,
            configuracao.primeiro_administrador,
            configuracao.nome_da_primeira_equipe,
            datetime.now(UTC),
        )
    if token:
        _registro.warning(
            "Primeiro administrador: abra /convite/%s no app para criar a conta de %s.",
            token,
            configuracao.primeiro_administrador,
        )


# --- erros: sempre {detalhe, erros} em português ---

_registro = logging.getLogger(__name__)


async def _responder_erro_inesperado(request: Request, chamar_proximo: Callable) -> Response:
    """Exceção não prevista vira o erro uniforme 500.

    Não pode ser um `exception_handler(Exception)`: o Starlette o executa no
    `ServerErrorMiddleware`, o mais externo, depois do CORS, e a resposta sairia sem os
    cabeçalhos CORS. A causa não vai para o cliente (§12); fica no log do servidor.
    """
    try:
        return await chamar_proximo(request)
    except Exception:
        _registro.exception("Erro inesperado em %s %s", request.method, request.url.path)
        return resposta_de_erro(500, "Erro interno do servidor.")


def _registrar_tratadores_de_erro(app: FastAPI) -> None:
    @app.exception_handler(DefinicaoInvalida)
    async def _definicao(_: Request, erro: DefinicaoInvalida) -> JSONResponse:
        return resposta_de_erro(
            422, "Definição inválida.", [ErroDeCampoSaida.de(e) for e in erro.erros]
        )

    @app.exception_handler(PastaInvalida)
    async def _pasta(_: Request, erro: PastaInvalida) -> JSONResponse:
        return resposta_de_erro(
            422, "Pasta inválida.", [ErroDeCampoSaida.de(e) for e in erro.erros]
        )

    @app.exception_handler(RegistroInvalido)
    async def _registro(_: Request, erro: RegistroInvalido) -> JSONResponse:
        return resposta_de_erro(
            422, "Registro inválido.", [ErroDeCampoSaida.de(e) for e in erro.erros]
        )

    @app.exception_handler(LoteInvalido)
    async def _lote(_: Request, erro: LoteInvalido) -> JSONResponse:
        # O `campo` leva o nome do formulário como prefixo: `proctor.umidade.formula`.
        erros = [
            ErroDeCampoSaida.de(e, prefixo=f"{formulario.nome}.")
            for formulario in erro.formularios
            for e in formulario.erros
        ]
        return resposta_de_erro(422, "Há formulários inválidos no lote; nada foi criado.", erros)

    @app.exception_handler(CargoInvalido)
    async def _cargo(_: Request, erro: CargoInvalido) -> JSONResponse:
        return resposta_de_erro(
            422, "Cargo inválido.", [ErroDeCampoSaida.de(e) for e in erro.erros]
        )

    @app.exception_handler(NaoAutenticado)
    async def _nao_autenticado(_: Request, erro: NaoAutenticado) -> JSONResponse:
        return resposta_de_erro(401, str(erro), codigo=erro.codigo)

    @app.exception_handler(TermosPendentes)
    async def _termos(_: Request, erro: TermosPendentes) -> JSONResponse:
        return resposta_de_erro(403, str(erro), codigo="termos_pendentes")

    @app.exception_handler(SemPermissao)
    async def _sem_permissao(_: Request, erro: SemPermissao) -> JSONResponse:
        return resposta_de_erro(403, str(erro), codigo="sem_permissao")

    @app.exception_handler(SemAcessoAEquipe)
    async def _sem_equipe(_: Request, erro: SemAcessoAEquipe) -> JSONResponse:
        return resposta_de_erro(403, str(erro), codigo="sem_equipe")

    @app.exception_handler(ConflitoDeRevisao)
    async def _conflito(_: Request, erro: ConflitoDeRevisao) -> JSONResponse:
        return resposta_de_erro(409, str(erro), codigo="revisao_desatualizada")

    @app.exception_handler(ValorInvalido)
    async def _valor(_: Request, erro: ValorInvalido) -> JSONResponse:
        return resposta_de_erro(422, str(erro))

    @app.exception_handler(NaoEncontrado)
    async def _nao_encontrado(_: Request, erro: NaoEncontrado) -> JSONResponse:
        return resposta_de_erro(404, str(erro))

    @app.exception_handler(ExclusaoBloqueada)
    async def _bloqueada(_: Request, erro: ExclusaoBloqueada) -> JSONResponse:
        return resposta_de_erro(409, str(erro))

    @app.exception_handler(ErroDeDominio)
    async def _dominio(_: Request, erro: ErroDeDominio) -> JSONResponse:
        return resposta_de_erro(400, str(erro))

    @app.exception_handler(RequestValidationError)
    async def _pydantic(_: Request, erro: RequestValidationError) -> JSONResponse:
        erros = [_erro_do_pydantic(e) for e in erro.errors()]
        return resposta_de_erro(422, "Requisição inválida.", erros)

    @app.exception_handler(ExcecaoHttp)
    async def _http(_: Request, erro: ExcecaoHttp) -> JSONResponse:
        return resposta_de_erro(
            erro.status_code, _DETALHES_HTTP.get(erro.status_code, "Erro na requisição.")
        )


_DETALHES_HTTP = {
    404: "Recurso não encontrado.",
    405: "Método não permitido.",
    413: "Requisição grande demais.",
    429: "Muitas requisições. Tente de novo em instantes.",
}

_MENSAGENS_DO_PYDANTIC = {
    "missing": "Campo obrigatório.",
    "json_invalid": "O corpo da requisição não é um JSON válido.",
    "int_parsing": "Deve ser um número inteiro.",
    "int_type": "Deve ser um número inteiro.",
    "string_type": "Deve ser um texto.",
    "bool_parsing": "Deve ser verdadeiro ou falso.",
    "date_from_datetime_parsing": "Deve ser uma data no formato AAAA-MM-DD.",
    "date_parsing": "Deve ser uma data no formato AAAA-MM-DD.",
    "date_type": "Deve ser uma data no formato AAAA-MM-DD.",
    "greater_than_equal": "Valor abaixo do mínimo permitido.",
    "less_than_equal": "Valor acima do máximo permitido.",
    "extra_forbidden": "Este campo não existe.",
    "model_attributes_type": "Deve ser um objeto JSON.",
    "list_type": "Deve ser uma lista.",
    "string_too_short": "O texto não pode ficar vazio.",
    "string_too_long": "Texto longo demais.",
    "too_long": "Itens demais.",
}


def _erro_do_pydantic(erro: Mapping[str, object]) -> ErroDeCampoSaida:
    localizacao = [str(parte) for parte in erro.get("loc", ())]
    # "body"/"query"/"path" dizem de onde veio; o front quer só o nome do campo.
    campo = ".".join(
        localizacao[1:]
        if localizacao and localizacao[0] in {"body", "query", "path"}
        else localizacao
    )
    mensagem = _MENSAGENS_DO_PYDANTIC.get(str(erro.get("type")), "Valor inválido.")
    return ErroDeCampoSaida(campo=campo or "requisicao", mensagem=mensagem)


def app_do_ambiente() -> FastAPI:
    """Fábrica do uvicorn (`--factory`): importar o módulo não abre banco nem conexão."""
    return criar_app(Configuracao.do_ambiente(), extensoes=descobrir_extensoes())


__all__ = ["Configuracao", "HTTPException", "app_do_ambiente", "criar_app", "descobrir_extensoes"]
