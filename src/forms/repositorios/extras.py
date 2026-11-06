"""Persistência de notificações, progresso do tour e nomes de pessoas (§2.16, §2.18).

Mesma regra dos outros repositórios: SQL parametrizado, conexão por parâmetro, sem commit aqui.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from forms.dominio.models import NaoEncontrado, ValorInvalido, ValorJson
from forms.infra.banco import Conexao


def _iso(momento: datetime) -> str:
    if momento.tzinfo is None:
        raise ValorInvalido("O horário deve vir com fuso (UTC).")
    return momento.isoformat(timespec="seconds")


@dataclass(frozen=True)
class Notificacao:
    id: int
    tipo: str
    referencia: dict[str, ValorJson]
    lida: bool
    criada_em: str


def criar_notificacao(
    conexao: Conexao,
    usuario_id: int,
    tipo: str,
    referencia: dict[str, ValorJson],
    agora: datetime,
) -> None:
    conexao.execute(
        "INSERT INTO notificacoes (grupo_id, usuario_id, tipo, referencia, criada_em)"
        " VALUES (%s, %s, %s, %s, %s)",
        (conexao.grupo_id, usuario_id, tipo, Jsonb(referencia), _iso(agora)),
    )


def listar_notificacoes(conexao: Conexao, usuario_id: int, limite: int) -> list[Notificacao]:
    linhas = conexao.execute(
        "SELECT id, tipo, referencia, lida_em IS NOT NULL AS lida, criada_em FROM notificacoes"
        " WHERE usuario_id = %s AND grupo_id = %s ORDER BY id DESC LIMIT %s",
        (usuario_id, conexao.grupo_id, limite),
    )
    return [Notificacao(**dict(linha)) for linha in linhas]


def contar_nao_lidas(conexao: Conexao, usuario_id: int) -> int:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n FROM notificacoes"
        " WHERE usuario_id = %s AND grupo_id = %s AND lida_em IS NULL",
        (usuario_id, conexao.grupo_id),
    ).fetchone()
    return int(linha["n"]) if linha else 0


def marcar_lida(conexao: Conexao, usuario_id: int, notificacao_id: int, agora: datetime) -> None:
    cursor = conexao.execute(
        "UPDATE notificacoes SET lida_em = COALESCE(lida_em, %s)"
        " WHERE id = %s AND usuario_id = %s AND grupo_id = %s",
        (_iso(agora), notificacao_id, usuario_id, conexao.grupo_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Notificação {notificacao_id} não encontrada.")


@dataclass(frozen=True)
class Progresso:
    tour_concluido: bool
    passo: int
    checklist_dispensado: bool


def obter_progresso(conexao: Conexao, usuario_id: int) -> Progresso:
    linha = conexao.execute(
        "SELECT tour_concluido, passo, checklist_dispensado FROM onboarding_progresso"
        " WHERE usuario_id = %s",
        (usuario_id,),
    ).fetchone()
    return Progresso(False, 0, False) if linha is None else Progresso(**dict(linha))


def gravar_progresso(
    conexao: Conexao, usuario_id: int, progresso: Progresso, agora: datetime
) -> None:
    conexao.execute(
        "INSERT INTO onboarding_progresso (usuario_id, tour_concluido, passo,"
        " checklist_dispensado, atualizado_em) VALUES (%s, %s, %s, %s, %s)"
        " ON CONFLICT (usuario_id) DO UPDATE SET tour_concluido = EXCLUDED.tour_concluido,"
        " passo = EXCLUDED.passo, checklist_dispensado = EXCLUDED.checklist_dispensado,"
        " atualizado_em = EXCLUDED.atualizado_em",
        (
            usuario_id,
            progresso.tour_concluido,
            progresso.passo,
            progresso.checklist_dispensado,
            _iso(agora),
        ),
    )


def nomes_de_usuarios(conexao: Conexao, ids: Collection[int]) -> dict[int, str]:
    """Nome de cada pessoa (para "por Lucas S." nos cartões). Pessoa removida não aparece."""
    if not ids:
        return {}
    linhas = conexao.execute(
        "SELECT id, nome FROM usuarios WHERE id = ANY(%s)", (sorted(set(ids)),)
    )
    return {int(linha["id"]): str(linha["nome"]) for linha in linhas}
