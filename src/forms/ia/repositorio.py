"""SQL do módulo de IA: configuração da equipe, documentos indexados, vetores, conversas e uso.

O módulo é opcional (AGENTS.md §5.1) e é dono das suas tabelas (`migracoes/0002_ia.sql`). Mesma
regra do núcleo: SQL parametrizado, conexão por parâmetro, `grupo_id` em toda consulta.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from forms.dominio.models import NaoEncontrado, ValorJson
from forms.infra.banco import Conexao


def _iso(momento: datetime) -> str:
    return momento.isoformat(timespec="seconds")


# --- configuração por equipe ---


@dataclass(frozen=True)
class ConfigGravada:
    ativa: bool
    consentimento_por: int | None
    consentimento_em: str | None
    provedor: str
    base_url: str | None
    modelo: str | None
    modelo_embeddings: str | None
    chave_cifrada: str | None


def obter_config(conexao: Conexao) -> ConfigGravada | None:
    linha = conexao.execute(
        "SELECT ativa, consentimento_por, consentimento_em, provedor, base_url, modelo,"
        " modelo_embeddings, chave_cifrada FROM config_ia_grupo WHERE grupo_id = %s",
        (conexao.grupo_id,),
    ).fetchone()
    return None if linha is None else ConfigGravada(**dict(linha))


def gravar_config(conexao: Conexao, config: ConfigGravada, agora: datetime) -> None:
    conexao.execute(
        "INSERT INTO config_ia_grupo (grupo_id, ativa, consentimento_por, consentimento_em,"
        " provedor, base_url, modelo, modelo_embeddings, chave_cifrada, atualizado_por,"
        " atualizado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (grupo_id) DO UPDATE SET ativa = EXCLUDED.ativa,"
        " consentimento_por = EXCLUDED.consentimento_por,"
        " consentimento_em = EXCLUDED.consentimento_em, provedor = EXCLUDED.provedor,"
        " base_url = EXCLUDED.base_url, modelo = EXCLUDED.modelo,"
        " modelo_embeddings = EXCLUDED.modelo_embeddings, chave_cifrada = EXCLUDED.chave_cifrada,"
        " atualizado_por = EXCLUDED.atualizado_por, atualizado_em = EXCLUDED.atualizado_em",
        (
            conexao.grupo_id,
            config.ativa,
            config.consentimento_por,
            config.consentimento_em,
            config.provedor,
            config.base_url,
            config.modelo,
            config.modelo_embeddings,
            config.chave_cifrada,
            conexao.usuario_id,
            _iso(agora),
        ),
    )


# --- uso (só contagens, nunca o conteúdo) ---


def registrar_uso(
    conexao: Conexao, provedor: str, tokens_entrada: int, tokens_saida: int, agora: datetime
) -> None:
    conexao.execute(
        "INSERT INTO uso_ia (grupo_id, usuario_id, provedor, tokens_entrada, tokens_saida, quando)"
        " VALUES (%s, %s, %s, %s, %s, %s)",
        (conexao.grupo_id, conexao.usuario_id, provedor, tokens_entrada, tokens_saida, _iso(agora)),
    )


@dataclass(frozen=True)
class Uso:
    chamadas: int
    tokens: int


def uso_desde(conexao: Conexao, desde: datetime, *, so_da_pessoa: bool) -> Uso:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(tokens_entrada + tokens_saida), 0) AS t FROM uso_ia"
        " WHERE grupo_id = %s AND quando >= %s AND (NOT %s OR usuario_id = %s)",
        (conexao.grupo_id, _iso(desde), so_da_pessoa, conexao.usuario_id),
    ).fetchone()
    return Uso(int(linha["n"]), int(linha["t"])) if linha else Uso(0, 0)


# --- documentos indexados ---


@dataclass(frozen=True)
class DocumentoGravado:
    id: int
    tipo: str
    origem_id: int
    formulario_id: int | None
    texto: str
    hash: str
    metadados: dict[str, ValorJson]
    criado_em: str | None
    atualizado_em: str


def documentos_existentes(conexao: Conexao) -> dict[tuple[str, int], tuple[int, str]]:
    """(tipo, origem) -> (id, hash) de tudo que já está indexado nesta equipe."""
    linhas = conexao.execute(
        "SELECT id, tipo, origem_id, hash FROM documentos_ia WHERE grupo_id = %s",
        (conexao.grupo_id,),
    )
    return {(linha["tipo"], linha["origem_id"]): (linha["id"], linha["hash"]) for linha in linhas}


def gravar_documento(
    conexao: Conexao,
    tipo: str,
    origem_id: int,
    formulario_id: int | None,
    texto: str,
    hash_: str,
    metadados: dict[str, ValorJson],
    criado_em: str | None,
    agora: datetime,
) -> int:
    linha = conexao.execute(
        "INSERT INTO documentos_ia (grupo_id, tipo, origem_id, formulario_id, texto, hash,"
        " metadados, criado_em, atualizado_em) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (grupo_id, tipo, origem_id) DO UPDATE SET texto = EXCLUDED.texto,"
        " hash = EXCLUDED.hash, metadados = EXCLUDED.metadados, formulario_id ="
        " EXCLUDED.formulario_id, atualizado_em = EXCLUDED.atualizado_em RETURNING id",
        (
            conexao.grupo_id,
            tipo,
            origem_id,
            formulario_id,
            texto,
            hash_,
            Jsonb(metadados),
            criado_em,
            _iso(agora),
        ),
    ).fetchone()
    assert linha is not None
    return int(linha["id"])


def apagar_documentos(conexao: Conexao, ids: Collection[int]) -> None:
    if ids:
        conexao.execute(
            "DELETE FROM documentos_ia WHERE grupo_id = %s AND id = ANY(%s)",
            (conexao.grupo_id, sorted(ids)),
        )


def apagar_todos_os_documentos(conexao: Conexao) -> None:
    conexao.execute("DELETE FROM documentos_ia WHERE grupo_id = %s", (conexao.grupo_id,))


def candidatos(
    conexao: Conexao,
    *,
    formulario_id: int | None,
    de: str | None,
    ate: str | None,
    limite: int,
) -> list[DocumentoGravado]:
    """Pré-filtro por metadados no SQL (equipe, formulário, datas), sempre antes de BM25 e
    vetores (§2.5). Os mais recentes primeiro, até `limite`."""
    linhas = conexao.execute(
        "SELECT id, tipo, origem_id, formulario_id, texto, hash, metadados, criado_em,"
        " atualizado_em FROM documentos_ia WHERE grupo_id = %s"
        " AND (%s::bigint IS NULL OR formulario_id = %s::bigint)"
        " AND (%s::timestamptz IS NULL OR COALESCE(criado_em, atualizado_em) >= %s::timestamptz)"
        " AND (%s::timestamptz IS NULL OR COALESCE(criado_em, atualizado_em) <= %s::timestamptz)"
        " ORDER BY atualizado_em DESC, id DESC LIMIT %s",
        (conexao.grupo_id, formulario_id, formulario_id, de, de, ate, ate, limite),
    )
    return [DocumentoGravado(**dict(linha)) for linha in linhas]


# --- vetores (pgvector) ---


def _como_vetor(valores: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in valores) + "]"


def documentos_sem_vetor(conexao: Conexao, modelo: str, limite: int) -> list[tuple[int, str]]:
    linhas = conexao.execute(
        "SELECT d.id, d.texto FROM documentos_ia d LEFT JOIN vetores_documentos v"
        " ON v.documento_id = d.id AND v.modelo = %s WHERE d.grupo_id = %s AND v.documento_id"
        " IS NULL ORDER BY d.id LIMIT %s",
        (modelo, conexao.grupo_id, limite),
    )
    return [(linha["id"], linha["texto"]) for linha in linhas]


def gravar_vetor(
    conexao: Conexao, documento_id: int, modelo: str, valores: Sequence[float]
) -> None:
    conexao.execute(
        "INSERT INTO vetores_documentos (documento_id, modelo, vetor) VALUES (%s, %s, %s::vector)"
        " ON CONFLICT (documento_id, modelo) DO UPDATE SET vetor = EXCLUDED.vetor",
        (documento_id, modelo, _como_vetor(valores)),
    )


def mais_proximos(
    conexao: Conexao, modelo: str, consulta: Sequence[float], ids: Collection[int], k: int
) -> list[tuple[int, float]]:
    """Cosseno (`<=>`) só entre os candidatos já filtrados: (documento, similaridade)."""
    if not ids:
        return []
    linhas = conexao.execute(
        "SELECT v.documento_id, 1 - (v.vetor <=> %s::vector) AS similaridade"
        " FROM vetores_documentos v JOIN documentos_ia d ON d.id = v.documento_id"
        " WHERE d.grupo_id = %s AND v.modelo = %s AND v.documento_id = ANY(%s)"
        " AND vector_dims(v.vetor) = %s ORDER BY v.vetor <=> %s::vector LIMIT %s",
        (
            _como_vetor(consulta),
            conexao.grupo_id,
            modelo,
            sorted(ids),
            len(consulta),
            _como_vetor(consulta),
            k,
        ),
    )
    return [(int(linha["documento_id"]), float(linha["similaridade"])) for linha in linhas]


# --- conversas ---


@dataclass(frozen=True)
class Conversa:
    id: int
    titulo: str
    criada_em: str


@dataclass(frozen=True)
class Mensagem:
    id: int
    papel: str
    texto: str
    citacoes: list[ValorJson]
    criada_em: str


def criar_conversa(conexao: Conexao, titulo: str, agora: datetime) -> int:
    linha = conexao.execute(
        "INSERT INTO conversas_ia (grupo_id, usuario_id, titulo, criada_em)"
        " VALUES (%s, %s, %s, %s) RETURNING id",
        (conexao.grupo_id, conexao.usuario_id, titulo[:80], _iso(agora)),
    ).fetchone()
    assert linha is not None
    return int(linha["id"])


def conversa_da_pessoa(conexao: Conexao, conversa_id: int) -> Conversa:
    """Só a dona da conversa a vê: a conversa é por pessoa, não da equipe."""
    linha = conexao.execute(
        "SELECT id, titulo, criada_em FROM conversas_ia"
        " WHERE id = %s AND grupo_id = %s AND usuario_id = %s",
        (conversa_id, conexao.grupo_id, conexao.usuario_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Conversa {conversa_id} não encontrada.")
    return Conversa(**dict(linha))


def listar_conversas(conexao: Conexao) -> list[Conversa]:
    linhas = conexao.execute(
        "SELECT id, titulo, criada_em FROM conversas_ia"
        " WHERE grupo_id = %s AND usuario_id = %s ORDER BY id DESC LIMIT 50",
        (conexao.grupo_id, conexao.usuario_id),
    )
    return [Conversa(**dict(linha)) for linha in linhas]


def apagar_conversa(conexao: Conexao, conversa_id: int) -> None:
    conversa_da_pessoa(conexao, conversa_id)
    conexao.execute("DELETE FROM conversas_ia WHERE id = %s", (conversa_id,))


def adicionar_mensagem(
    conexao: Conexao,
    conversa_id: int,
    papel: str,
    texto: str,
    citacoes: Sequence[ValorJson],
    agora: datetime,
) -> None:
    conexao.execute(
        "INSERT INTO mensagens_ia (conversa_id, papel, texto, citacoes, criada_em)"
        " VALUES (%s, %s, %s, %s, %s)",
        (conversa_id, papel, texto, Jsonb(list(citacoes)), _iso(agora)),
    )


def listar_mensagens(conexao: Conexao, conversa_id: int, limite: int = 200) -> list[Mensagem]:
    conversa_da_pessoa(conexao, conversa_id)
    linhas = conexao.execute(
        "SELECT id, papel, texto, citacoes, criada_em FROM mensagens_ia"
        " WHERE conversa_id = %s ORDER BY id LIMIT %s",
        (conversa_id, limite),
    )
    return [Mensagem(**dict(linha)) for linha in linhas]


def apagar_vetores_do_documento(conexao: Conexao, documento_id: int) -> None:
    conexao.execute("DELETE FROM vetores_documentos WHERE documento_id = %s", (documento_id,))


@dataclass(frozen=True)
class RegistroParaIndexar:
    id: int
    formulario_id: int
    formulario: str
    versao_id: int
    dados: dict[str, ValorJson]
    criado_em: str
    atualizado_em: str
    criado_por: int | None


def registros_para_indexar(
    conexao: Conexao, depois_do_id: int, limite: int
) -> list[RegistroParaIndexar]:
    linhas = conexao.execute(
        "SELECT r.id, r.formulario_id, f.nome AS formulario, r.versao_id, r.dados, r.criado_em,"
        " r.atualizado_em, r.criado_por FROM registros r JOIN formularios f ON f.id ="
        " r.formulario_id WHERE r.grupo_id = %s AND r.id > %s ORDER BY r.id LIMIT %s",
        (conexao.grupo_id, depois_do_id, limite),
    )
    return [RegistroParaIndexar(**dict(linha)) for linha in linhas]
