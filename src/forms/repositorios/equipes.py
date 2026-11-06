"""Persistência de pessoas, equipes, cargos, convites e consentimentos (AGENTS.md §2.12, §2.13).

Mesma regra do `repositorio.py`: SQL sempre parametrizado, conexão por parâmetro, nada de
commit aqui. As tabelas `grupos`, `usuarios`, `membros_grupo`, `convites` e `consentimentos`
não têm RLS porque são lidas *antes* de a equipe da conexão ser declarada (login); as
consultas que dependem da equipe filtram por `grupo_id` mesmo assim.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from forms.dominio.models import CargoInvalido, ErroDeCampo, NaoEncontrado, ValorInvalido
from forms.infra.banco import Conexao
from forms.repositorios.formularios import chave_do_nome


def _iso(momento: datetime) -> str:
    if momento.tzinfo is None:
        raise ValorInvalido("O horário deve vir com fuso (UTC).")
    return momento.isoformat(timespec="seconds")


@dataclass(frozen=True)
class Grupo:
    id: int
    nome: str
    criado_em: str


@dataclass(frozen=True)
class Usuario:
    id: int
    logto_sub: str
    nome: str
    email: str | None
    ativo: bool
    criado_em: str
    ultimo_acesso_em: str | None


@dataclass(frozen=True)
class Cargo:
    id: int
    nome: str
    descricao: str
    padrao: bool
    permissoes: tuple[str, ...]
    pessoas: int = 0


@dataclass(frozen=True)
class Membro:
    usuario_id: int
    nome: str
    email: str | None
    cargo_id: int
    cargo_nome: str
    ativo: bool
    entrou_em: str


@dataclass(frozen=True)
class Convite:
    id: int
    email: str
    cargo_id: int
    cargo_nome: str
    criado_em: str
    expira_em: str
    usado_em: str | None
    revogado_em: str | None
    grupo_id: int = 0


# --- equipes ---


def criar_grupo(conexao: Conexao, nome: str, agora: datetime) -> Grupo:
    linha = conexao.execute(
        "INSERT INTO grupos (nome, criado_em) VALUES (%s, %s) RETURNING id, nome, criado_em",
        (nome.strip(), _iso(agora)),
    ).fetchone()
    assert linha is not None
    return Grupo(**dict(linha))


def obter_grupo(conexao: Conexao, grupo_id: int) -> Grupo:
    linha = conexao.execute(
        "SELECT id, nome, criado_em FROM grupos WHERE id = %s", (grupo_id,)
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Equipe {grupo_id} não encontrada.")
    return Grupo(**dict(linha))


def renomear_grupo(conexao: Conexao, grupo_id: int, nome: str) -> None:
    conexao.execute("UPDATE grupos SET nome = %s WHERE id = %s", (nome.strip(), grupo_id))


def contar_grupos(conexao: Conexao) -> int:
    linha = conexao.execute("SELECT COUNT(*) AS n FROM grupos").fetchone()
    return int(linha["n"]) if linha else 0


# --- pessoas ---

_COLUNAS_DO_USUARIO = "id, logto_sub, nome, email, ativo, criado_em, ultimo_acesso_em"


def obter_usuario_por_sub(conexao: Conexao, sub: str) -> Usuario | None:
    linha = conexao.execute(
        f"SELECT {_COLUNAS_DO_USUARIO} FROM usuarios WHERE logto_sub = %s",  # noqa: S608
        (sub,),
    ).fetchone()
    return None if linha is None else Usuario(**dict(linha))


def obter_usuario(conexao: Conexao, usuario_id: int) -> Usuario:
    linha = conexao.execute(
        f"SELECT {_COLUNAS_DO_USUARIO} FROM usuarios WHERE id = %s",  # noqa: S608
        (usuario_id,),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Pessoa {usuario_id} não encontrada.")
    return Usuario(**dict(linha))


def criar_usuario(
    conexao: Conexao, sub: str, nome: str, email: str | None, agora: datetime
) -> Usuario:
    linha = conexao.execute(
        "INSERT INTO usuarios (logto_sub, nome, email, criado_em, ultimo_acesso_em)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (sub, nome, email, _iso(agora), _iso(agora)),
    ).fetchone()
    assert linha is not None
    return obter_usuario(conexao, linha["id"])


def registrar_acesso(
    conexao: Conexao, usuario_id: int, agora: datetime, nome: str | None, email: str | None
) -> None:
    """Atualiza o último acesso e, se o Logto trouxe, o nome e o e-mail."""
    conexao.execute(
        "UPDATE usuarios SET ultimo_acesso_em = %s, nome = COALESCE(%s, nome),"
        " email = COALESCE(%s, email) WHERE id = %s",
        (_iso(agora), nome, email, usuario_id),
    )


def apagar_usuario(conexao: Conexao, usuario_id: int) -> None:
    """Exclusão da conta: as chaves estrangeiras anonimizam a autoria (`SET NULL`) (§2.15)."""
    conexao.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))


# --- membros ---


def obter_membro(conexao: Conexao, grupo_id: int, usuario_id: int) -> Membro | None:
    linha = conexao.execute(
        _SELECT_MEMBRO + " WHERE m.grupo_id = %s AND m.usuario_id = %s", (grupo_id, usuario_id)
    ).fetchone()
    return None if linha is None else Membro(**dict(linha))


def listar_membros(conexao: Conexao, grupo_id: int) -> list[Membro]:
    linhas = conexao.execute(
        _SELECT_MEMBRO + " WHERE m.grupo_id = %s ORDER BY u.nome, u.id", (grupo_id,)
    )
    return [Membro(**dict(linha)) for linha in linhas]


_SELECT_MEMBRO = """
    SELECT m.usuario_id, u.nome, u.email, m.cargo_id, c.nome AS cargo_nome, m.ativo,
           m.entrou_em
    FROM membros_grupo m
    JOIN usuarios u ON u.id = m.usuario_id
    JOIN cargos c ON c.id = m.cargo_id"""


def grupos_do_usuario(conexao: Conexao, usuario_id: int) -> list[tuple[Grupo, int, bool]]:
    """(equipe, cargo_id, ativo) de cada equipe da pessoa."""
    linhas = conexao.execute(
        "SELECT g.id, g.nome, g.criado_em, m.cargo_id, m.ativo FROM membros_grupo m"
        " JOIN grupos g ON g.id = m.grupo_id WHERE m.usuario_id = %s ORDER BY g.id",
        (usuario_id,),
    )
    return [
        (Grupo(linha["id"], linha["nome"], linha["criado_em"]), linha["cargo_id"], linha["ativo"])
        for linha in linhas
    ]


def adicionar_membro(
    conexao: Conexao, grupo_id: int, usuario_id: int, cargo_id: int, agora: datetime
) -> None:
    conexao.execute(
        "INSERT INTO membros_grupo (grupo_id, usuario_id, cargo_id, entrou_em)"
        " VALUES (%s, %s, %s, %s)",
        (grupo_id, usuario_id, cargo_id, _iso(agora)),
    )


def trocar_cargo_do_membro(conexao: Conexao, grupo_id: int, usuario_id: int, cargo_id: int) -> None:
    cursor = conexao.execute(
        "UPDATE membros_grupo SET cargo_id = %s WHERE grupo_id = %s AND usuario_id = %s",
        (cargo_id, grupo_id, usuario_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado("Pessoa não encontrada nesta equipe.")


def definir_membro_ativo(conexao: Conexao, grupo_id: int, usuario_id: int, ativo: bool) -> None:
    cursor = conexao.execute(
        "UPDATE membros_grupo SET ativo = %s WHERE grupo_id = %s AND usuario_id = %s",
        (ativo, grupo_id, usuario_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado("Pessoa não encontrada nesta equipe.")


def remover_membro(conexao: Conexao, grupo_id: int, usuario_id: int) -> None:
    conexao.execute(
        "DELETE FROM membros_grupo WHERE grupo_id = %s AND usuario_id = %s",
        (grupo_id, usuario_id),
    )


def contar_pessoas_com_permissao(
    conexao: Conexao, grupo_id: int, permissao: str, *, ignorar_usuario: int | None = None
) -> int:
    """Pessoas ativas cujo cargo tem a permissão: a regra "sempre existe um administrador"."""
    linha = conexao.execute(
        """
        SELECT COUNT(*) AS n FROM membros_grupo m
        JOIN cargo_permissoes p ON p.cargo_id = m.cargo_id AND p.permissao = %s
        WHERE m.grupo_id = %s AND m.ativo AND (%s::bigint IS NULL OR m.usuario_id <> %s::bigint)
        """,
        (permissao, grupo_id, ignorar_usuario, ignorar_usuario),
    ).fetchone()
    return int(linha["n"]) if linha else 0


# --- cargos ---


def criar_cargo(
    conexao: Conexao,
    grupo_id: int,
    nome: str,
    descricao: str,
    permissoes: Collection[str],
    *,
    padrao: bool = False,
) -> Cargo:
    nome = nome.strip()
    repetido = conexao.execute(
        "SELECT 1 FROM cargos WHERE grupo_id = %s AND nome_chave = %s",
        (grupo_id, chave_do_nome(nome)),
    ).fetchone()
    if repetido:
        raise CargoInvalido((ErroDeCampo("nome", "Já existe um cargo com este nome."),))
    linha = conexao.execute(
        "INSERT INTO cargos (grupo_id, nome, nome_chave, descricao, padrao)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (grupo_id, nome, chave_do_nome(nome), descricao.strip(), padrao),
    ).fetchone()
    assert linha is not None
    _gravar_permissoes(conexao, linha["id"], permissoes)
    return obter_cargo(conexao, grupo_id, linha["id"])


def atualizar_cargo(
    conexao: Conexao,
    grupo_id: int,
    cargo_id: int,
    nome: str,
    descricao: str,
    permissoes: Collection[str],
) -> Cargo:
    obter_cargo(conexao, grupo_id, cargo_id)
    nome = nome.strip()
    repetido = conexao.execute(
        "SELECT 1 FROM cargos WHERE grupo_id = %s AND nome_chave = %s AND id <> %s",
        (grupo_id, chave_do_nome(nome), cargo_id),
    ).fetchone()
    if repetido:
        raise CargoInvalido((ErroDeCampo("nome", "Já existe um cargo com este nome."),))
    conexao.execute(
        "UPDATE cargos SET nome = %s, nome_chave = %s, descricao = %s"
        " WHERE id = %s AND grupo_id = %s",
        (nome, chave_do_nome(nome), descricao.strip(), cargo_id, grupo_id),
    )
    conexao.execute("DELETE FROM cargo_permissoes WHERE cargo_id = %s", (cargo_id,))
    _gravar_permissoes(conexao, cargo_id, permissoes)
    return obter_cargo(conexao, grupo_id, cargo_id)


def _gravar_permissoes(conexao: Conexao, cargo_id: int, permissoes: Collection[str]) -> None:
    with conexao.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO cargo_permissoes (cargo_id, permissao) VALUES (%s, %s)",
            [(cargo_id, p) for p in sorted(set(permissoes))],
        )


_SELECT_CARGO = """
    SELECT c.id, c.nome, c.descricao, c.padrao,
           COALESCE((SELECT array_agg(p.permissao ORDER BY p.permissao)
                     FROM cargo_permissoes p WHERE p.cargo_id = c.id), '{}') AS permissoes,
           (SELECT COUNT(*) FROM membros_grupo m WHERE m.cargo_id = c.id AND m.ativo) AS pessoas
    FROM cargos c"""


def obter_cargo(conexao: Conexao, grupo_id: int, cargo_id: int) -> Cargo:
    linha = conexao.execute(
        _SELECT_CARGO + " WHERE c.id = %s AND c.grupo_id = %s", (cargo_id, grupo_id)
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Cargo {cargo_id} não encontrado.")
    return _cargo_da_linha(linha)


def listar_cargos(conexao: Conexao, grupo_id: int) -> list[Cargo]:
    linhas = conexao.execute(_SELECT_CARGO + " WHERE c.grupo_id = %s ORDER BY c.id", (grupo_id,))
    return [_cargo_da_linha(linha) for linha in linhas]


def _cargo_da_linha(linha: Mapping[str, object]) -> Cargo:
    permissoes = linha["permissoes"]
    assert isinstance(permissoes, list)
    return Cargo(
        id=int(str(linha["id"])),
        nome=str(linha["nome"]),
        descricao=str(linha["descricao"]),
        padrao=bool(linha["padrao"]),
        permissoes=tuple(str(p) for p in permissoes),
        pessoas=int(str(linha["pessoas"])),
    )


def permissoes_do_cargo(conexao: Conexao, cargo_id: int) -> frozenset[str]:
    linhas = conexao.execute(
        "SELECT permissao FROM cargo_permissoes WHERE cargo_id = %s", (cargo_id,)
    )
    return frozenset(linha[0] for linha in linhas)


def contar_membros_do_cargo(conexao: Conexao, cargo_id: int) -> int:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n FROM membros_grupo WHERE cargo_id = %s", (cargo_id,)
    ).fetchone()
    return int(linha["n"]) if linha else 0


def excluir_cargo(conexao: Conexao, grupo_id: int, cargo_id: int) -> None:
    cursor = conexao.execute(
        "DELETE FROM cargos WHERE id = %s AND grupo_id = %s", (cargo_id, grupo_id)
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Cargo {cargo_id} não encontrado.")


# --- convites ---


def criar_convite(
    conexao: Conexao,
    grupo_id: int,
    email: str,
    cargo_id: int,
    token_hash: str,
    criado_por: int | None,
    agora: datetime,
    expira_em: datetime,
) -> int:
    linha = conexao.execute(
        "INSERT INTO convites (grupo_id, email, cargo_id, token_hash, criado_por, criado_em,"
        " expira_em) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (grupo_id, email.strip(), cargo_id, token_hash, criado_por, _iso(agora), _iso(expira_em)),
    ).fetchone()
    assert linha is not None
    return int(linha["id"])


_SELECT_CONVITE = """
    SELECT v.id, v.email, v.cargo_id, c.nome AS cargo_nome, v.criado_em, v.expira_em,
           v.usado_em, v.revogado_em, v.grupo_id
    FROM convites v JOIN cargos c ON c.id = v.cargo_id"""


def obter_convite_por_hash(conexao: Conexao, token_hash: str) -> Convite | None:
    # LEFT JOIN de propósito: quem aceita um convite ainda não tem equipe, e `cargos` tem Row Level
    # Security. Com INNER JOIN o papel do aplicativo não enxergaria o cargo e o convite "sumiria".
    linha = conexao.execute(
        "SELECT v.id, v.email, v.cargo_id, COALESCE(c.nome, '') AS cargo_nome, v.criado_em,"
        " v.expira_em, v.usado_em, v.revogado_em, v.grupo_id"
        " FROM convites v LEFT JOIN cargos c ON c.id = v.cargo_id WHERE v.token_hash = %s",
        (token_hash,),
    ).fetchone()
    return None if linha is None else Convite(**dict(linha))


def listar_convites(conexao: Conexao, grupo_id: int) -> list[Convite]:
    linhas = conexao.execute(
        _SELECT_CONVITE + " WHERE v.grupo_id = %s AND v.usado_em IS NULL AND v.revogado_em IS NULL"
        " ORDER BY v.id DESC",
        (grupo_id,),
    )
    return [Convite(**dict(linha)) for linha in linhas]


def revogar_convite(conexao: Conexao, grupo_id: int, convite_id: int, agora: datetime) -> None:
    cursor = conexao.execute(
        "UPDATE convites SET revogado_em = %s WHERE id = %s AND grupo_id = %s"
        " AND usado_em IS NULL AND revogado_em IS NULL",
        (_iso(agora), convite_id, grupo_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Convite {convite_id} não encontrado.")


def marcar_convite_usado(conexao: Conexao, convite_id: int, agora: datetime) -> bool:
    """Atômico: só um aceite consegue marcar (`usado_em IS NULL`)."""
    cursor = conexao.execute(
        "UPDATE convites SET usado_em = %s WHERE id = %s AND usado_em IS NULL"
        " AND revogado_em IS NULL AND expira_em > %s",
        (_iso(agora), convite_id, _iso(agora)),
    )
    return cursor.rowcount == 1


# --- consentimentos (LGPD) ---


def registrar_consentimento(
    conexao: Conexao, usuario_id: int, documento: str, versao: str, agora: datetime
) -> None:
    conexao.execute(
        "INSERT INTO consentimentos (usuario_id, documento, versao, aceito_em)"
        " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (usuario_id, documento, versao, _iso(agora)),
    )


def listar_consentimentos(conexao: Conexao, usuario_id: int) -> list[tuple[str, str, str]]:
    linhas = conexao.execute(
        "SELECT documento, versao, aceito_em FROM consentimentos WHERE usuario_id = %s ORDER BY id",
        (usuario_id,),
    )
    return [(linha["documento"], linha["versao"], linha["aceito_em"]) for linha in linhas]


def versoes_aceitas(conexao: Conexao, usuario_id: int) -> set[tuple[str, str]]:
    return {(d, v) for d, v, _ in listar_consentimentos(conexao, usuario_id)}
