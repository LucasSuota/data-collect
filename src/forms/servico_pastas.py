"""Casos de uso das pastas (AGENTS.md §2.10): organizam formulários numa árvore.

Pasta não muda definição, versão, registro nem referência entre formulários; por isso mover um
formulário só troca a coluna `pasta_id`.
"""

import sqlite3
from datetime import datetime

from forms import repositorio
from forms.models import ErroDeCampo, ExclusaoBloqueada, Pasta, PastaInvalida
from forms.servico_base import transacao

_DESTINO_INEXISTENTE = "A pasta de destino não existe."
_CICLO = "Uma pasta não pode ser movida para dentro dela mesma ou de uma subpasta."


def criar_pasta(
    conexao: sqlite3.Connection, nome: str, pasta_pai_id: int | None, agora: datetime
) -> Pasta:
    with transacao(conexao):
        _conferir_destino(conexao, pasta_pai_id, "pasta_pai_id")
        return repositorio.criar_pasta(conexao, nome, pasta_pai_id, agora)


def listar_pastas(conexao: sqlite3.Connection) -> list[Pasta]:
    """Lista plana; o front monta a árvore a partir de `pasta_pai_id`."""
    return repositorio.listar_pastas(conexao)


def atualizar_pasta(
    conexao: sqlite3.Connection, pasta_id: int, nome: str, pasta_pai_id: int | None
) -> Pasta:
    """Renomeia e/ou move a pasta (substitui os dois campos, como o `PUT` do §2.10)."""
    repositorio.obter_pasta(conexao, pasta_id)  # 404 antes de qualquer 422
    with transacao(conexao):
        _conferir_destino(conexao, pasta_pai_id, "pasta_pai_id")
        # Mover para dentro de si mesma ou de uma descendente criaria um ciclo na árvore.
        if pasta_pai_id is not None and repositorio.pasta_esta_na_subarvore(
            conexao, pasta_pai_id, pasta_id
        ):
            raise PastaInvalida((ErroDeCampo("pasta_pai_id", _CICLO),))
        return repositorio.atualizar_pasta(conexao, pasta_id, nome, pasta_pai_id)


def excluir_pasta(conexao: sqlite3.Connection, pasta_id: int) -> None:
    """Só se estiver vazia: nada é apagado em cascata (subpasta ou formulário bloqueia)."""
    pasta = repositorio.obter_pasta(conexao, pasta_id)
    subpastas = repositorio.contar_subpastas(conexao, pasta_id)
    if subpastas:
        raise ExclusaoBloqueada(
            f"A pasta '{pasta.nome}' tem {subpastas} subpasta(s) e não pode ser excluída."
        )
    formularios = repositorio.contar_formularios_da_pasta(conexao, pasta_id)
    if formularios:
        raise ExclusaoBloqueada(
            f"A pasta '{pasta.nome}' tem {formularios} formulário(s) e não pode ser excluída."
        )
    with transacao(conexao):
        repositorio.excluir_pasta(conexao, pasta_id)


def mover_formulario(conexao: sqlite3.Connection, formulario_id: int, pasta_id: int | None) -> None:
    """`pasta_id` nulo leva o formulário para a raiz."""
    repositorio.obter_formulario(conexao, formulario_id)  # 404 antes de qualquer 422
    with transacao(conexao):
        _conferir_destino(conexao, pasta_id, "pasta_id")
        repositorio.mover_formulario(conexao, formulario_id, pasta_id)


def _conferir_destino(conexao: sqlite3.Connection, pasta_id: int | None, campo: str) -> None:
    if pasta_id is not None and not repositorio.pasta_existe(conexao, pasta_id):
        raise PastaInvalida((ErroDeCampo(campo, _DESTINO_INEXISTENTE),))
