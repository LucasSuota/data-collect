"""Dependências do FastAPI: identidade, conexão com a equipe declarada e permissão (§2.12, §2.13).

A conexão da requisição sai do pool já com o contexto (equipe, pessoa, permissões) conferido no
banco: o cabeçalho `X-Equipe` do cliente é só um pedido, e a pertença à equipe é verificada.
A matriz endpoint → permissão (`api_permissoes.py`) é aplicada aqui, uma vez, para toda rota.
"""

import math
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg_pool import ConnectionPool

from forms import servico_equipes
from forms.api_permissoes import classificar
from forms.api_seguranca import LIMITES_POR_ROTA
from forms.auth import Identidade, ValidadorDeToken
from forms.banco import Conexao
from forms.models import (
    Contexto,
    LimiteExcedido,
    NaoAutenticado,
    SemAcessoAEquipe,
    SemPermissao,
    ValorInvalido,
)

esquema_bearer = HTTPBearer(
    auto_error=False, scheme_name="Bearer", description="Token de acesso do Logto (10 minutos)."
)


def obter_agora() -> datetime:
    return datetime.now(UTC)


def obter_identidade(
    request: Request,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
) -> Identidade:
    validador: ValidadorDeToken | None = request.app.state.validador
    if validador is None:
        # Falha fechada: sem Logto configurado a API não aceita ninguém.
        raise NaoAutenticado("A autenticação não está configurada.", "autenticacao_indisponivel")
    return validador.validar(credenciais.credentials if credenciais else "")


async def obter_conexao(
    request: Request,
    identidade: Annotated[Identidade, Depends(obter_identidade)],
    agora: Annotated[datetime, Depends(obter_agora)],
    equipe: Annotated[int | None, Header(alias="X-Equipe")] = None,
) -> AsyncIterator[Conexao]:
    """Uma conexão por requisição, com a equipe declarada.

    Um semáforo do tamanho do pool espera **sem ocupar thread**: se a espera fosse dentro de
    `pool.connection()` (síncrona), com mais pedidos que conexões todas as threads do FastAPI
    ficariam presas aguardando, e quem já tem conexão nunca conseguiria uma thread para terminar
    (deadlock até o tempo limite do pool).
    """
    pool = request.app.state.pool
    rota = (request.method, request.scope["route"].path)
    gestor = request.app.state.gestor
    perfil = gestor.perfil if gestor is not None else None
    async with request.app.state.limite_do_pool:
        conexao = await run_in_threadpool(pool.getconn)
        try:
            await run_in_threadpool(
                _declarar_contexto, conexao, classificar(rota), identidade, equipe, agora, perfil
            )
            yield conexao
        finally:
            await run_in_threadpool(_devolver, pool, conexao)


def _devolver(pool: ConnectionPool[Conexao], conexao: Conexao) -> None:
    conexao.definir_contexto(None)  # a conexão volta ao pool sem equipe
    pool.putconn(conexao)


def _declarar_contexto(
    conexao: Conexao,
    classe: str,
    identidade: Identidade,
    equipe: int | None,
    agora: datetime,
    perfil: Callable[[str], tuple[str | None, str | None]] | None,
) -> None:
    usuario = servico_equipes.identificar(
        conexao, identidade.sub, identidade.nome, identidade.email, agora, perfil
    )
    if not usuario.ativo:
        raise SemAcessoAEquipe("Esta conta está desativada.")
    if classe == "sem_equipe":
        conexao.definir_contexto(Contexto(None, usuario.id))
        return

    grupo_id = equipe if equipe is not None else _unica_equipe(conexao, usuario.id)
    contexto = servico_equipes.contexto_da_pessoa(conexao, usuario.id, grupo_id)
    servico_equipes.exigir_termos(conexao, usuario.id)
    conexao.definir_contexto(contexto)
    if classe not in {"qualquer_membro", "publica"} and not _permitida(contexto, classe):
        raise SemPermissao(classe)


def _unica_equipe(conexao: Conexao, usuario_id: int) -> int:
    ativas = [e for e in servico_equipes.minhas_equipes(conexao, usuario_id) if e.ativa]
    if len(ativas) == 1:
        return ativas[0].id
    if not ativas:
        raise SemAcessoAEquipe("Você ainda não faz parte de nenhuma equipe. Peça um convite.")
    raise ValorInvalido("Escolha a equipe (cabeçalho X-Equipe).")


def _permitida(contexto: Contexto, especificacao: str) -> bool:
    """`a|b` significa "qualquer uma das duas"."""
    return any(contexto.tem(p) for p in especificacao.split("|"))


def autorizar(request: Request, conexao: Annotated[Conexao, Depends(obter_conexao)]) -> None:
    """Dependência do roteador inteiro: força a conferência acima e aplica o limite de taxa das
    rotas caras (por pessoa; §12)."""
    rota = (request.method, request.scope["route"].path)
    limite = LIMITES_POR_ROTA.get(rota)
    if limite is None:
        return
    espera = request.app.state.limitador.tentar(
        (str(conexao.usuario_id), f"{rota[0]} {rota[1]}"), limite
    )
    if espera is not None:
        raise LimiteExcedido(math.ceil(espera))


DepConexao = Annotated[Conexao, Depends(obter_conexao)]
DepAgora = Annotated[datetime, Depends(obter_agora)]
DepIdentidade = Annotated[Identidade, Depends(obter_identidade)]
