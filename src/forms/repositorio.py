"""Persistência em SQLite: único módulo que fala SQL (AGENTS.md §5.1).

Sempre com parâmetros (`?`), nunca f-string em SQL com dado externo. A conexão entra por
parâmetro em cada função; não há conexão global.
"""

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path

from forms.models import ErroDeDominio

type Migracao = Callable[[sqlite3.Connection], None]


class EsquemaMaisNovo(ErroDeDominio):
    """O banco foi criado por uma versão do app mais nova que esta."""


# Esquema 1 (AGENTS.md §5.2). Datas em texto ISO; JSON em colunas de texto.
# Exclusões: sem ON DELETE o SQLite recusa (RESTRICT), o que protege os bloqueios de
# exclusão do §2.7 mesmo se o serviço esquecer de checar.
_ESQUEMA_1 = (
    """
    CREATE TABLE formularios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL UNIQUE,
        criado_em TEXT NOT NULL
    )
    """,
    # Apagar o formulário apaga suas versões; só é possível sem registros (RESTRICT abaixo).
    """
    CREATE TABLE versoes_formulario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        formulario_id INTEGER NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
        numero INTEGER NOT NULL,
        definicao TEXT NOT NULL,
        publicada_em TEXT NOT NULL,
        UNIQUE (formulario_id, numero)
    )
    """,
    """
    CREATE TABLE registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        formulario_id INTEGER NOT NULL REFERENCES formularios (id),
        versao_id INTEGER NOT NULL REFERENCES versoes_formulario (id),
        dados TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )
    """,
    "CREATE INDEX registros_por_versao ON registros (formulario_id, versao_id)",
    """
    CREATE TABLE dependencias_formulario (
        formulario_id INTEGER NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
        depende_de_id INTEGER NOT NULL REFERENCES formularios (id),
        PRIMARY KEY (formulario_id, depende_de_id)
    )
    """,
    # Apagar um registro apaga as referências que ele fazia; apagar o destino é recusado.
    """
    CREATE TABLE referencias_registro (
        registro_id INTEGER NOT NULL REFERENCES registros (id) ON DELETE CASCADE,
        campo_id TEXT NOT NULL,
        destino_id INTEGER NOT NULL REFERENCES registros (id),
        PRIMARY KEY (registro_id, campo_id)
    )
    """,
    "CREATE INDEX referencias_por_destino ON referencias_registro (destino_id)",
    # `registro_id` e `campo_id` ficam nulos até o anexo ser vinculado a um registro (§2.8).
    # `caminho` é relativo à pasta de dados e usa sempre "/".
    """
    CREATE TABLE anexos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registro_id INTEGER REFERENCES registros (id),
        campo_id TEXT,
        caminho TEXT NOT NULL,
        largura INTEGER NOT NULL,
        altura INTEGER NOT NULL,
        tamanho_bytes INTEGER NOT NULL,
        criado_em TEXT NOT NULL
    )
    """,
    "CREATE INDEX anexos_por_registro ON anexos (registro_id)",
)


def _criar_esquema_1(conexao: sqlite3.Connection) -> None:
    for comando in _ESQUEMA_1:
        conexao.execute(comando)


# A migração de posição N leva o banco da versão N para a N+1. Nunca edite uma migração
# já publicada: o banco do usuário persiste entre versões do app; acrescente uma nova.
MIGRACOES: tuple[Migracao, ...] = (_criar_esquema_1,)
VERSAO_ATUAL_DO_ESQUEMA = len(MIGRACOES)


def abrir_conexao(caminho: Path | str) -> sqlite3.Connection:
    """Abre o banco com as chaves estrangeiras ligadas e o esquema atualizado."""
    conexao = sqlite3.connect(caminho)
    try:
        conexao.row_factory = sqlite3.Row
        # O SQLite deixa as chaves estrangeiras desligadas por padrão, por conexão.
        conexao.execute("PRAGMA foreign_keys = ON")
        migrar(conexao)
    except BaseException:
        # Sem fechar, no Windows o arquivo ficaria travado depois da recusa.
        conexao.close()
        raise
    return conexao


def migrar(conexao: sqlite3.Connection, migracoes: Sequence[Migracao] = MIGRACOES) -> None:
    """Aplica as migrações pendentes, cada uma numa transação junto com o `user_version`."""
    versao_do_banco = conexao.execute("PRAGMA user_version").fetchone()[0]
    if versao_do_banco > len(migracoes):
        raise EsquemaMaisNovo(
            f"O banco foi criado por uma versão mais nova do aplicativo (esquema {versao_do_banco},"
            f" esta versão conhece até o {len(migracoes)}). Atualize o aplicativo."
        )

    for numero, migracao in enumerate(migracoes[versao_do_banco:], start=versao_do_banco + 1):
        # BEGIN explícito: sem ele, o módulo `sqlite3` não abre transação para DDL e uma
        # falha no meio deixaria o banco pela metade.
        conexao.execute("BEGIN")
        try:
            migracao(conexao)
            # PRAGMA não aceita parâmetro (?); `numero` é um int gerado aqui, nunca texto externo.
            conexao.execute(f"PRAGMA user_version = {numero}")
            conexao.commit()
        except BaseException:
            conexao.rollback()
            raise
