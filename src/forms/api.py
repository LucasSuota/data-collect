"""A API HTTP: monta o FastAPI, o token por execução, o CORS e o formato de erro uniforme.

Ponto de entrada: `uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000` (AGENTS.md §4).
Pydantic e HTTP só existem aqui e em `api_esquemas.py`/`api_rotas.py`; toda regra de negócio
fica em `servico.py` e abaixo.
"""

import logging
import os
import secrets
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as ExcecaoHttp
from starlette.routing import BaseRoute, Match

from forms import servico
from forms.api_esquemas import ErroDeCampoSaida
from forms.api_extensoes import Extensao, descobrir_extensoes, resposta_de_erro
from forms.api_rotas import CABECALHO_DO_TOKEN, roteador
from forms.models import (
    DefinicaoInvalida,
    ErroDeDominio,
    ExclusaoBloqueada,
    FotoInvalida,
    LoteInvalido,
    NaoEncontrado,
    PastaInvalida,
    RegistroInvalido,
    ValorInvalido,
)

ORIGENS_PADRAO = ("http://localhost:5173", "http://127.0.0.1:5173")


@dataclass(frozen=True)
class Configuracao:
    banco: Path
    pasta_de_dados: Path
    # Token por execução (§4.1). Sem token e sem dispensa, a API recusa tudo (falha fechada).
    token: str | None
    dispensar_token: bool
    origens_cors: tuple[str, ...]

    def __post_init__(self) -> None:
        if "*" in self.origens_cors:
            raise ValueError(
                "O CORS nunca pode liberar '*': liste as origens do front (AGENTS.md §12)."
            )

    @classmethod
    def do_ambiente(cls, ambiente: Mapping[str, str] | None = None) -> "Configuracao":
        """Lê `FORMS_DB_PATH`, `FORMS_DATA_DIR`, `FORMS_TOKEN`, `FORMS_SKIP_TOKEN`
        e `FORMS_CORS_ORIGINS`."""
        if ambiente is None:
            load_dotenv()  # o `.env` (fora do git) complementa o ambiente real
            ambiente = os.environ
        banco = Path(ambiente.get("FORMS_DB_PATH") or "forms.db")
        pasta = Path(ambiente.get("FORMS_DATA_DIR") or banco.resolve().parent)
        origens = tuple(
            o.strip() for o in (ambiente.get("FORMS_CORS_ORIGINS") or "").split(",") if o.strip()
        )
        return cls(
            banco=banco,
            pasta_de_dados=pasta,
            token=ambiente.get("FORMS_TOKEN") or None,
            dispensar_token=(ambiente.get("FORMS_SKIP_TOKEN") or "").strip().lower()
            in {"1", "true", "sim"},
            origens_cors=origens or ORIGENS_PADRAO,
        )


def criar_app(
    configuracao: Configuracao,
    pasta_do_front: Path | None = None,
    extensoes: Sequence[Extensao] = (),
) -> FastAPI:
    """Monta a aplicação. Nada abre banco aqui: a conexão é aberta por requisição.

    Com `pasta_do_front` (o `frontend/dist`), serve o front na mesma origem da API (app
    instalado, §4.1): então não há CORS, e a página e os arquivos estáticos não pedem token (o
    navegador não manda cabeçalho ao carregar o `index.html`). Toda rota da API continua exigindo.

    `extensoes` são as rotas dos módulos opcionais (`ia/`, `rag/`); sem elas o app é o mesmo, só
    sem essas rotas. Elas entram antes do front e do token, então também exigem o token.
    """

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
        _limpar_anexos_orfaos(configuracao)
        yield

    app = FastAPI(
        title="data-collect",
        version="0.1.0",
        description=(
            "API local. Todo erro tem o formato `{detalhe, erros: [{campo, mensagem}]}`. "
            f"Envie o token no cabeçalho `{CABECALHO_DO_TOKEN}`."
        ),
        lifespan=ciclo_de_vida,
    )
    app.state.configuracao = configuracao
    app.include_router(roteador)
    for extensao in extensoes:
        app.include_router(extensao.roteador)
        for tipo, tratador in extensao.tratadores.items():
            app.add_exception_handler(tipo, tratador)
    # As rotas da API (e a documentação) ficam registradas ANTES do front, que vira a "sobra".
    rotas_da_api = list(app.routes)
    if pasta_do_front is not None:
        app.mount("/", StaticFiles(directory=pasta_do_front, html=True), name="front")
    _registrar_tratadores_de_erro(app)

    # Ordem importa: o último adicionado fica por fora. O CORS vai por fora do token, para o
    # preflight (OPTIONS, que não leva o token) passar e o 401 também receber os cabeçalhos CORS.
    # O tratador de erro inesperado fica por dentro de ambos, pelo mesmo motivo: o 500 precisa
    # passar pelo CORS, senão o navegador o esconde e o front acha que o servidor caiu.
    app.middleware("http")(_responder_erro_inesperado)
    app.middleware("http")(_exigir_token(configuracao, rotas_da_api, pasta_do_front is not None))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(configuracao.origens_cors),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[CABECALHO_DO_TOKEN, "Content-Type"],
        expose_headers=["Content-Disposition"],
        allow_credentials=False,
    )
    return app


# --- token ---


def _exigir_token(
    configuracao: Configuracao, rotas_da_api: list[BaseRoute], serve_o_front: bool
) -> Callable:
    def e_do_front(request: Request) -> bool:
        """Só é "do front" o que nenhuma rota da API reconhece: nunca um caminho da API."""
        return serve_o_front and not any(
            rota.matches(request.scope)[0] != Match.NONE for rota in rotas_da_api
        )

    async def middleware(request: Request, chamar_proximo: Callable) -> Response:
        if request.method == "OPTIONS" or configuracao.dispensar_token or e_do_front(request):
            return await chamar_proximo(request)
        enviado = request.headers.get(CABECALHO_DO_TOKEN, "")
        if configuracao.token and secrets.compare_digest(enviado, configuracao.token):
            return await chamar_proximo(request)
        # Mesma mensagem para ausente e errado: não ensina nada a quem tenta adivinhar.
        return resposta_de_erro(401, "Token ausente ou inválido.")

    return middleware


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

    @app.exception_handler(FotoInvalida)
    async def _foto(_: Request, erro: FotoInvalida) -> JSONResponse:
        return resposta_de_erro(
            422, "Foto inválida.", [ErroDeCampoSaida(campo="arquivo", mensagem=str(erro))]
        )

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
    413: "Arquivo grande demais.",
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


# --- inicialização ---


def _limpar_anexos_orfaos(configuracao: Configuracao) -> None:
    """Na inicialização remove os anexos nunca vinculados há mais de 24 h (§2.8)."""
    with closing(servico.abrir_banco(configuracao.banco)) as conexao:
        servico.limpar_anexos_orfaos(conexao, configuracao.pasta_de_dados, datetime.now(UTC))


# O `app` do uvicorn. Importar o módulo não abre banco nem cria arquivo.
app = criar_app(Configuracao.do_ambiente(), extensoes=descobrir_extensoes())

__all__ = ["Configuracao", "HTTPException", "app", "criar_app", "descobrir_extensoes"]
