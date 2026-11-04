"""Conexão com o PostgreSQL e migrações do esquema (AGENTS.md §4, §5.2).

SQL de consulta fica em `repositorio.py`; aqui só se abre a conexão, declara a equipe da conexão
(para o Row Level Security) e aplica os arquivos de `migracoes/`. A conexão entra por parâmetro
em cada função (§9.9): não há conexão global.
"""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from typing import Any

import psycopg
from psycopg import sql
from psycopg.adapt import Loader
from psycopg.rows import RowMaker
from psycopg_pool import ConnectionPool

from forms.models import Contexto, ErroDeDominio

# Conexões por instância da API. O semáforo da API tem o mesmo tamanho (ver `api_dependencias`).
TAMANHO_DO_POOL = 20

# Nome fixo da trava de migração: duas instâncias subindo juntas não migram ao mesmo tempo.
_TRAVA_DE_MIGRACAO = 7_100_001


class EsquemaMaisNovo(ErroDeDominio):
    """O banco foi criado por uma versão do app mais nova que esta."""


class EsquemaDesatualizado(ErroDeDominio):
    """O banco não recebeu todas as migrações deste app (`/readyz` responde 503)."""


class SemContexto(ErroDeDominio):
    """A conexão não declarou a equipe: nenhuma consulta de dados pode rodar assim."""


class Linha(dict[str, Any]):
    """Linha do resultado: acessa por nome (`linha["id"]`) e por posição (`linha[0]`)."""

    def __getitem__(self, chave: Any) -> Any:
        if isinstance(chave, int):
            return list(self.values())[chave]
        return super().__getitem__(chave)


def _fabrica_de_linhas(cursor: Any) -> RowMaker[Linha]:
    descricao = cursor.description
    nomes = [coluna.name for coluna in descricao] if descricao is not None else []

    def montar(valores: Sequence[Any]) -> Linha:
        return Linha(zip(nomes, valores, strict=False))

    return montar


class _InstanteEmTexto(Loader):
    """`timestamptz` volta como texto ISO em UTC (`2026-11-02T10:00:00+00:00`).

    Mantém o contrato da API e dos modelos (datas em texto ISO) sem converter linha a linha; a
    comparação e a ordenação continuam acontecendo no banco, com o tipo real.
    """

    def load(self, data: Any) -> str:
        texto = bytes(data).decode()
        # O Postgres devolve `2026-11-02 10:00:00+00` (sessão em UTC) ou com fração de segundo.
        momento = datetime.fromisoformat(
            texto.replace("+00", "+00:00") if texto.endswith("+00") else texto
        )
        return momento.isoformat(timespec="seconds")


class Conexao(psycopg.Connection[Linha]):
    """Conexão que sabe de qual equipe e de quem é a requisição (`contexto`)."""

    contexto: Contexto | None = None

    def definir_contexto(self, contexto: Contexto | None) -> None:
        """Declara a equipe da conexão: o RLS do Postgres lê `app.grupo_id` (§2.13)."""
        self.contexto = contexto
        valor = "" if contexto is None or contexto.grupo_id is None else str(contexto.grupo_id)
        self.execute("SELECT set_config('app.grupo_id', %s, false)", (valor,))

    @property
    def grupo_id(self) -> int:
        if self.contexto is None or self.contexto.grupo_id is None:
            raise SemContexto("A conexão não declarou a equipe (grupo).")
        return self.contexto.grupo_id

    @property
    def usuario_id(self) -> int | None:
        return None if self.contexto is None else self.contexto.usuario_id


def abrir_conexao(dsn: str, *, migrar_esquema: bool = False) -> Conexao:
    """Abre uma conexão (autocommit: a atomicidade é de `servico_base.transacao`)."""
    conexao = Conexao.connect(dsn, autocommit=True, row_factory=_fabrica_de_linhas)
    try:
        _configurar(conexao)
        if migrar_esquema:
            migrar(conexao)
    except BaseException:
        conexao.close()
        raise
    return conexao


def _configurar(conexao: Conexao) -> None:
    conexao.execute("SET TIME ZONE 'UTC'")
    conexao.adapters.register_loader("timestamptz", _InstanteEmTexto)


def criar_pool(
    dsn: str, *, tamanho_maximo: int = 10, papel: str | None = None
) -> ConnectionPool[Conexao]:
    """Pool da API: uma conexão por requisição (`with pool.connection()`).

    `papel` troca o papel da sessão (`SET ROLE`). Em produção a API já conecta como `forms_app`;
    os testes conectam como dono do banco e assumem `forms_app` aqui, para o Row Level Security
    valer também neles (o superusuário o ignoraria e esconderia bugs de isolamento).
    """

    def configurar(conexao: Conexao) -> None:
        _configurar(conexao)
        if papel is not None:
            # Identificador montado por `psycopg.sql` (nunca por texto): é o único jeito seguro.
            comando = sql.SQL("SET ROLE {}").format(sql.Identifier(papel))
            conexao.execute(comando)

    return ConnectionPool(
        dsn,
        connection_class=Conexao,
        min_size=1,
        max_size=tamanho_maximo,
        kwargs={"autocommit": True, "row_factory": _fabrica_de_linhas},
        configure=configurar,
        open=True,
    )


# --- migrações ---

_NOME_DA_MIGRACAO = re.compile(r"(\d{4})_[a-z0-9_]+\.sql")


@dataclass(frozen=True)
class Migracao:
    numero: int
    nome: str
    sql: str


def migracoes_do_pacote() -> tuple[Migracao, ...]:
    """Os arquivos `NNNN_nome.sql` de `forms/migracoes`, em ordem. Nunca edite um já publicado:
    o banco persiste entre versões do app, então a mudança é um arquivo novo (§5.2)."""
    pasta = resources.files("forms").joinpath("migracoes")
    encontradas = []
    for arquivo in pasta.iterdir():
        casou = _NOME_DA_MIGRACAO.fullmatch(arquivo.name)
        if casou:
            encontradas.append(
                Migracao(int(casou.group(1)), arquivo.name, arquivo.read_text(encoding="utf-8"))
            )
    return tuple(sorted(encontradas, key=lambda m: m.numero))


def migrar(
    conexao: Conexao,
    migracoes: Sequence[Migracao] | None = None,
    *,
    aplicar: Callable[[Migracao], None] | None = None,
) -> int:
    """Aplica as migrações pendentes, cada uma numa transação junto do registro da versão.

    `pg_advisory_lock` impede duas instâncias de migrarem ao mesmo tempo. Devolve quantas
    migrações foram aplicadas.
    """
    lista = tuple(migracoes) if migracoes is not None else migracoes_do_pacote()
    conexao.execute("SELECT pg_advisory_lock(%s)", (_TRAVA_DE_MIGRACAO,))
    try:
        conexao.execute(
            "CREATE TABLE IF NOT EXISTS esquema_versao ("
            " numero INTEGER PRIMARY KEY, nome TEXT NOT NULL, aplicada_em TIMESTAMPTZ NOT NULL"
            " DEFAULT now())"
        )
        feitas = {
            linha[0] for linha in conexao.execute("SELECT numero FROM esquema_versao").fetchall()
        }
        mais_nova = max(feitas, default=0)
        conhecida = max((m.numero for m in lista), default=0)
        if mais_nova > conhecida:
            raise EsquemaMaisNovo(
                f"O banco foi criado por uma versão mais nova do aplicativo (esquema {mais_nova},"
                f" esta versão conhece até o {conhecida}). Atualize o aplicativo."
            )
        aplicadas = 0
        for migracao in lista:
            if migracao.numero in feitas:
                continue
            with conexao.transaction():
                if aplicar is not None:
                    aplicar(migracao)
                else:
                    conexao.execute(sql.SQL(migracao.sql))  # DDL de arquivo versionado
                conexao.execute(
                    "INSERT INTO esquema_versao (numero, nome) VALUES (%s, %s)",
                    (migracao.numero, migracao.nome),
                )
            aplicadas += 1
        return aplicadas
    finally:
        conexao.execute("SELECT pg_advisory_unlock(%s)", (_TRAVA_DE_MIGRACAO,))
