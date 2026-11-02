"""Persistência em SQLite: único módulo que fala SQL (AGENTS.md §5.1).

Sempre com parâmetros (`?`), nunca f-string em SQL com dado externo. A conexão entra por
parâmetro em cada função; não há conexão global.
"""

import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePath

from forms.models import (
    Definicao,
    DefinicaoInvalida,
    ErroDeCampo,
    ErroDeDominio,
    Formulario,
    NaoEncontrado,
    Registro,
    ValorInvalido,
    ValorJson,
    Versao,
)

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


def chave_do_nome(nome: str) -> str:
    """Forma comparável do nome: sem espaços nas pontas, sem diferenciar caixa nem a forma
    (composta ou decomposta) dos acentos. O `lower()` do SQLite só entende ASCII, então a chave
    é calculada aqui e guardada numa coluna com índice único."""
    return unicodedata.normalize("NFC", nome.strip()).casefold()


def _adicionar_chave_unica_do_nome(conexao: sqlite3.Connection) -> None:
    conexao.execute("ALTER TABLE formularios ADD COLUMN nome_chave TEXT")
    for id_do_formulario, nome in conexao.execute("SELECT id, nome FROM formularios").fetchall():
        conexao.execute(
            "UPDATE formularios SET nome_chave = ? WHERE id = ?",
            (chave_do_nome(nome), id_do_formulario),
        )
    conexao.execute("CREATE UNIQUE INDEX formularios_por_nome_chave ON formularios (nome_chave)")


def _criar_vetores_dos_trechos(conexao: sqlite3.Connection) -> None:
    # Embeddings dos trechos dos procedimentos (§2.5). `chave` é o hash do modelo e do texto do
    # trecho, então trecho alterado ou outro modelo de embeddings geram outra chave e o vetor
    # antigo é só descartado. `vetor` são float32 little-endian (4 bytes por dimensão).
    conexao.execute("CREATE TABLE vetores_trechos (chave TEXT PRIMARY KEY, vetor BLOB NOT NULL)")


# A migração de posição N leva o banco da versão N para a N+1. Nunca edite uma migração
# já publicada: o banco do usuário persiste entre versões do app; acrescente uma nova.
MIGRACOES: tuple[Migracao, ...] = (
    _criar_esquema_1,
    _adicionar_chave_unica_do_nome,
    _criar_vetores_dos_trechos,
)
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


# --- convenções das consultas ---
# Estas funções não fazem commit: a transação é de quem chama (o serviço), para que várias
# operações (por exemplo, a cascata de recálculo) entrem ou saiam juntas.
# O relógio entra por parâmetro (`agora`, sempre em UTC); o repositório nunca lê a hora.


def _iso(momento: datetime) -> str:
    if momento.tzinfo is None:
        raise ValorInvalido("O horário deve vir com fuso (UTC).")
    # Mesmo formato em todas as colunas de data: a comparação de texto vira comparação de tempo.
    return momento.isoformat(timespec="seconds")


@dataclass(frozen=True)
class ResumoDeFormulario:
    id: int
    nome: str
    criado_em: str
    versao_atual_id: int | None
    versao_atual_numero: int | None


@dataclass(frozen=True)
class ResumoDeVersao:
    id: int
    numero: int
    publicada_em: str


# --- formulários e versões ---


def criar_formulario(conexao: sqlite3.Connection, nome: str, agora: datetime) -> Formulario:
    nome = nome.strip()
    if not nome:
        raise DefinicaoInvalida((ErroDeCampo("nome", "O nome do formulário é obrigatório."),))
    chave = chave_do_nome(nome)
    if conexao.execute("SELECT 1 FROM formularios WHERE nome_chave = ?", (chave,)).fetchone():
        raise DefinicaoInvalida((ErroDeCampo("nome", "Já existe um formulário com este nome."),))
    cursor = conexao.execute(
        "INSERT INTO formularios (nome, nome_chave, criado_em) VALUES (?, ?, ?)",
        (nome, chave, _iso(agora)),
    )
    return obter_formulario(conexao, _id_inserido(cursor))


def obter_formulario(conexao: sqlite3.Connection, formulario_id: int) -> Formulario:
    linha = conexao.execute(
        "SELECT id, nome, criado_em FROM formularios WHERE id = ?", (formulario_id,)
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Formulário {formulario_id} não encontrado.")
    return Formulario(linha["id"], linha["nome"], linha["criado_em"])


def obter_formulario_por_nome(conexao: sqlite3.Connection, nome: str) -> Formulario | None:
    linha = conexao.execute(
        "SELECT id, nome, criado_em FROM formularios WHERE nome_chave = ?", (chave_do_nome(nome),)
    ).fetchone()
    return None if linha is None else Formulario(linha["id"], linha["nome"], linha["criado_em"])


def listar_formularios(conexao: sqlite3.Connection) -> list[ResumoDeFormulario]:
    linhas = conexao.execute(
        """
        SELECT f.id, f.nome, f.criado_em, v.id AS versao_atual_id, v.numero AS versao_atual_numero
        FROM formularios f
        LEFT JOIN versoes_formulario v
            ON v.formulario_id = f.id
            AND v.numero = (SELECT MAX(numero) FROM versoes_formulario WHERE formulario_id = f.id)
        ORDER BY f.id
        """
    )
    return [ResumoDeFormulario(**dict(linha)) for linha in linhas]


def excluir_formulario(conexao: sqlite3.Connection, formulario_id: int) -> None:
    """Apaga o formulário e suas versões. O banco recusa (IntegrityError) se houver registros
    ou dependentes; quem chama confere antes para devolver 409 com mensagem clara (§2.7)."""
    cursor = conexao.execute("DELETE FROM formularios WHERE id = ?", (formulario_id,))
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Formulário {formulario_id} não encontrado.")


def inserir_versao(
    conexao: sqlite3.Connection, formulario_id: int, definicao: Definicao, agora: datetime
) -> Versao:
    """Publica a próxima versão (número anterior + 1). Não existe como alterar uma versão
    publicada: este módulo não tem `update` nem `delete` de versão (AGENTS.md §3.3)."""
    obter_formulario(conexao, formulario_id)
    cursor = conexao.execute(
        """
        INSERT INTO versoes_formulario (formulario_id, numero, definicao, publicada_em)
        VALUES (?, (SELECT COALESCE(MAX(numero), 0) + 1 FROM versoes_formulario
                    WHERE formulario_id = ?), ?, ?)
        """,
        (
            formulario_id,
            formulario_id,
            json.dumps(definicao.para_json(), ensure_ascii=False),
            _iso(agora),
        ),
    )
    return obter_versao(conexao, _id_inserido(cursor))


def obter_versao(
    conexao: sqlite3.Connection, versao_id: int, formulario_id: int | None = None
) -> Versao:
    """Com `formulario_id`, só acha a versão se ela pertencer a esse formulário."""
    linha = conexao.execute(
        """
        SELECT id, formulario_id, numero, definicao, publicada_em FROM versoes_formulario
        WHERE id = ? AND (? IS NULL OR formulario_id = ?)
        """,
        (versao_id, formulario_id, formulario_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Versão {versao_id} não encontrada.")
    return _versao_da_linha(linha)


def obter_versao_atual(conexao: sqlite3.Connection, formulario_id: int) -> Versao:
    linha = conexao.execute(
        """
        SELECT id, formulario_id, numero, definicao, publicada_em FROM versoes_formulario
        WHERE formulario_id = ? ORDER BY numero DESC LIMIT 1
        """,
        (formulario_id,),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"O formulário {formulario_id} ainda não tem versão publicada.")
    return _versao_da_linha(linha)


def listar_versoes(conexao: sqlite3.Connection, formulario_id: int) -> list[ResumoDeVersao]:
    linhas = conexao.execute(
        "SELECT id, numero, publicada_em FROM versoes_formulario WHERE formulario_id = ?"
        " ORDER BY numero",
        (formulario_id,),
    )
    return [ResumoDeVersao(**dict(linha)) for linha in linhas]


def _versao_da_linha(linha: sqlite3.Row) -> Versao:
    return Versao(
        id=linha["id"],
        formulario_id=linha["formulario_id"],
        numero=linha["numero"],
        definicao=Definicao.de_json(json.loads(linha["definicao"])),
        publicada_em=linha["publicada_em"],
    )


def _id_inserido(cursor: sqlite3.Cursor) -> int:
    # `lastrowid` é `None` só quando nada foi inserido, o que não acontece após um INSERT.
    assert cursor.lastrowid is not None
    return cursor.lastrowid


# --- registros ---

_CAMPO_FILTRAVEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class FiltroDeIgualdade:
    campo: str
    valor: str | bool
    # Campo calculado guarda `{"valor", "erro"}`: o filtro olha só o `valor`.
    calculado: bool = False


@dataclass(frozen=True)
class PaginaDeRegistros:
    itens: tuple[Registro, ...]
    total: int


def inserir_registro(
    conexao: sqlite3.Connection,
    formulario_id: int,
    versao_id: int,
    dados: Mapping[str, ValorJson],
    agora: datetime,
) -> Registro:
    momento = _iso(agora)
    cursor = conexao.execute(
        "INSERT INTO registros (formulario_id, versao_id, dados, criado_em, atualizado_em)"
        " VALUES (?, ?, ?, ?, ?)",
        (formulario_id, versao_id, json.dumps(dados, ensure_ascii=False), momento, momento),
    )
    return obter_registro(conexao, _id_inserido(cursor))


def obter_registro(conexao: sqlite3.Connection, registro_id: int) -> Registro:
    linha = conexao.execute(
        "SELECT id, formulario_id, versao_id, dados, criado_em, atualizado_em"
        " FROM registros WHERE id = ?",
        (registro_id,),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")
    return _registro_da_linha(linha)


def atualizar_registro(
    conexao: sqlite3.Connection, registro_id: int, dados: Mapping[str, ValorJson], agora: datetime
) -> Registro:
    """Substitui todos os dados (sem mesclar); a versão de origem e a criação não mudam."""
    cursor = conexao.execute(
        "UPDATE registros SET dados = ?, atualizado_em = ? WHERE id = ?",
        (json.dumps(dados, ensure_ascii=False), _iso(agora), registro_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")
    return obter_registro(conexao, registro_id)


def excluir_registro(conexao: sqlite3.Connection, registro_id: int) -> None:
    cursor = conexao.execute("DELETE FROM registros WHERE id = ?", (registro_id,))
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")


def contar_registros(conexao: sqlite3.Connection, formulario_id: int) -> int:
    return conexao.execute(
        "SELECT COUNT(*) FROM registros WHERE formulario_id = ?", (formulario_id,)
    ).fetchone()[0]


def listar_registros(
    conexao: sqlite3.Connection,
    versao_id: int,
    *,
    limite: int,
    deslocamento: int,
    filtros: Sequence[FiltroDeIgualdade] = (),
    campos_permitidos: Collection[str] = frozenset(),
    criado_de: str | None = None,
    criado_ate: str | None = None,
) -> PaginaDeRegistros:
    """Registros de uma versão, do mais recente para o mais antigo, com `total` do filtro.

    O nome de cada campo filtrado precisa estar em `campos_permitidos` (calculado pelo serviço
    a partir da definição) e ter formato de identificador: só então entra no caminho JSON, que
    mesmo assim vai como parâmetro. Valores nunca são concatenados.
    """
    if limite < 1 or deslocamento < 0:
        raise ValorInvalido(
            "O limite deve ser pelo menos 1 e o deslocamento não pode ser negativo."
        )

    condicoes = ["versao_id = ?"]
    parametros: list[object] = [versao_id]
    for filtro in filtros:
        condicoes.append("json_extract(dados, ?) = ?")
        parametros.extend(
            (_caminho_json(filtro, campos_permitidos), _valor_do_filtro(filtro.valor))
        )
    if criado_de is not None:
        condicoes.append("criado_em >= ?")
        parametros.append(criado_de)
    if criado_ate is not None:
        condicoes.append("criado_em <= ?")
        parametros.append(criado_ate)
    onde = " AND ".join(condicoes)  # só fragmentos fixos acima; todos os valores são parâmetros

    total = conexao.execute(f"SELECT COUNT(*) FROM registros WHERE {onde}", parametros).fetchone()[
        0
    ]
    linhas = conexao.execute(
        f"SELECT id, formulario_id, versao_id, dados, criado_em, atualizado_em FROM registros"
        f" WHERE {onde} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*parametros, limite, deslocamento],
    )
    return PaginaDeRegistros(tuple(_registro_da_linha(linha) for linha in linhas), total)


def _caminho_json(filtro: FiltroDeIgualdade, campos_permitidos: Collection[str]) -> str:
    if filtro.campo not in campos_permitidos or not _CAMPO_FILTRAVEL.fullmatch(filtro.campo):
        raise ValorInvalido(f"Não é possível filtrar pelo campo '{filtro.campo}'.")
    return f'$."{filtro.campo}"' + (".valor" if filtro.calculado else "")


def _valor_do_filtro(valor: str | bool) -> str | int:
    # O JSON guarda `true`/`false`, que o `json_extract` devolve como 1/0.
    return int(valor) if isinstance(valor, bool) else valor


def _registro_da_linha(linha: sqlite3.Row) -> Registro:
    return Registro(
        id=linha["id"],
        formulario_id=linha["formulario_id"],
        versao_id=linha["versao_id"],
        dados=json.loads(linha["dados"]),
        criado_em=linha["criado_em"],
        atualizado_em=linha["atualizado_em"],
    )


# --- relações entre formulários e entre registros (§2.7) ---

# Teto de segurança das consultas recursivas. O grafo é acíclico por construção (ciclo é
# rejeitado ao publicar), então isto só protege contra dado corrompido.
_PROFUNDIDADE_MAXIMA = 1000


def registrar_dependencias(
    conexao: sqlite3.Connection, formulario_id: int, depende_de_ids: Collection[int]
) -> None:
    """Chamado ao publicar. O vínculo fica enquanto o formulário existir (versões antigas
    e seus registros ainda apontam para a origem)."""
    conexao.executemany(
        "INSERT OR IGNORE INTO dependencias_formulario (formulario_id, depende_de_id)"
        " VALUES (?, ?)",
        [(formulario_id, origem) for origem in sorted(depende_de_ids)],
    )


def listar_dependencias(conexao: sqlite3.Connection) -> list[tuple[int, int]]:
    """Todas as arestas `(formulario, depende_de)`, para o serviço detectar ciclo."""
    linhas = conexao.execute(
        "SELECT formulario_id, depende_de_id FROM dependencias_formulario"
        " ORDER BY formulario_id, depende_de_id"
    )
    return [(linha[0], linha[1]) for linha in linhas]


def formularios_dependentes(
    conexao: sqlite3.Connection, formulario_id: int, *, transitivo: bool
) -> list[int]:
    """Formulários que dependem deste, os mais próximos primeiro."""
    linhas = conexao.execute(
        """
        WITH RECURSIVE alcance(id, nivel) AS (
            SELECT formulario_id, 1 FROM dependencias_formulario WHERE depende_de_id = ?
            UNION ALL
            SELECT d.formulario_id, a.nivel + 1
            FROM dependencias_formulario d JOIN alcance a ON d.depende_de_id = a.id
            WHERE ? AND a.nivel < ?
        )
        SELECT id FROM alcance GROUP BY id ORDER BY MAX(nivel), id
        """,
        (formulario_id, transitivo, _PROFUNDIDADE_MAXIMA),
    )
    return [linha[0] for linha in linhas]


def substituir_referencias(
    conexao: sqlite3.Connection, registro_id: int, referencias: Mapping[str, int]
) -> None:
    """Deixa as referências do registro exatamente como no último salvamento (campo -> destino)."""
    conexao.execute("DELETE FROM referencias_registro WHERE registro_id = ?", (registro_id,))
    conexao.executemany(
        "INSERT INTO referencias_registro (registro_id, campo_id, destino_id) VALUES (?, ?, ?)",
        [(registro_id, campo, destino) for campo, destino in referencias.items()],
    )


def obter_referencias(conexao: sqlite3.Connection, registro_id: int) -> dict[str, int]:
    linhas = conexao.execute(
        "SELECT campo_id, destino_id FROM referencias_registro WHERE registro_id = ?"
        " ORDER BY campo_id",
        (registro_id,),
    )
    return {linha[0]: linha[1] for linha in linhas}


def registros_que_referenciam(conexao: sqlite3.Connection, registro_id: int) -> list[int]:
    linhas = conexao.execute(
        "SELECT DISTINCT registro_id FROM referencias_registro WHERE destino_id = ?"
        " ORDER BY registro_id",
        (registro_id,),
    )
    return [linha[0] for linha in linhas]


def registros_dependentes(conexao: sqlite3.Connection, registro_id: int) -> list[int]:
    """Dependentes diretos e indiretos, em ordem de recálculo da cascata.

    Um registro só vem depois de todos aqueles dos quais depende: a ordenação usa o caminho
    *mais longo* até ele, para um destino alcançado por dois caminhos (diamante) ser
    recalculado só depois dos dois.
    """
    linhas = conexao.execute(
        """
        WITH RECURSIVE alcance(id, nivel) AS (
            SELECT registro_id, 1 FROM referencias_registro WHERE destino_id = ?
            UNION ALL
            SELECT r.registro_id, a.nivel + 1
            FROM referencias_registro r JOIN alcance a ON r.destino_id = a.id
            WHERE a.nivel < ?
        )
        SELECT id FROM alcance GROUP BY id ORDER BY MAX(nivel), id
        """,
        (registro_id, _PROFUNDIDADE_MAXIMA),
    )
    return [linha[0] for linha in linhas]


# --- anexos (metadados das fotos, §2.8) ---


@dataclass(frozen=True)
class Anexo:
    id: int
    registro_id: int | None
    campo_id: str | None
    caminho: str
    largura: int
    altura: int
    tamanho_bytes: int
    criado_em: str


def criar_anexo(
    conexao: sqlite3.Connection,
    caminho: str | PurePath,
    *,
    largura: int,
    altura: int,
    tamanho_bytes: int,
    agora: datetime,
) -> Anexo:
    """Anexo nasce solto (sem registro): o upload acontece antes de o registro existir."""
    cursor = conexao.execute(
        "INSERT INTO anexos (caminho, largura, altura, tamanho_bytes, criado_em)"
        " VALUES (?, ?, ?, ?, ?)",
        (_caminho_portavel(caminho), largura, altura, tamanho_bytes, _iso(agora)),
    )
    return obter_anexo(conexao, _id_inserido(cursor))


def obter_anexo(conexao: sqlite3.Connection, anexo_id: int) -> Anexo:
    linha = conexao.execute(
        "SELECT id, registro_id, campo_id, caminho, largura, altura, tamanho_bytes, criado_em"
        " FROM anexos WHERE id = ?",
        (anexo_id,),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Anexo {anexo_id} não encontrado.")
    return Anexo(**dict(linha))


def vincular_anexo(
    conexao: sqlite3.Connection, anexo_id: int, registro_id: int, campo_id: str
) -> Anexo:
    if obter_anexo(conexao, anexo_id).registro_id is not None:
        raise ValorInvalido("O anexo já está vinculado a um registro.")
    conexao.execute(
        "UPDATE anexos SET registro_id = ?, campo_id = ? WHERE id = ?",
        (registro_id, campo_id, anexo_id),
    )
    return obter_anexo(conexao, anexo_id)


def desvincular_anexo(conexao: sqlite3.Connection, anexo_id: int) -> Anexo:
    obter_anexo(conexao, anexo_id)
    conexao.execute(
        "UPDATE anexos SET registro_id = NULL, campo_id = NULL WHERE id = ?", (anexo_id,)
    )
    return obter_anexo(conexao, anexo_id)


def apagar_anexo(conexao: sqlite3.Connection, anexo_id: int) -> None:
    """Apaga só a linha; o arquivo `.webp` é apagado pelo serviço, depois do commit (§2.8)."""
    cursor = conexao.execute("DELETE FROM anexos WHERE id = ?", (anexo_id,))
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Anexo {anexo_id} não encontrado.")


def listar_anexos_do_registro(conexao: sqlite3.Connection, registro_id: int) -> list[Anexo]:
    linhas = conexao.execute(
        "SELECT id, registro_id, campo_id, caminho, largura, altura, tamanho_bytes, criado_em"
        " FROM anexos WHERE registro_id = ? ORDER BY id",
        (registro_id,),
    )
    return [Anexo(**dict(linha)) for linha in linhas]


def listar_anexos_orfaos(conexao: sqlite3.Connection, *, criados_antes_de: datetime) -> list[Anexo]:
    """Anexos nunca vinculados criados *antes* do instante dado (quem chama passa agora - 24 h)."""
    linhas = conexao.execute(
        "SELECT id, registro_id, campo_id, caminho, largura, altura, tamanho_bytes, criado_em"
        " FROM anexos WHERE registro_id IS NULL AND criado_em < ? ORDER BY id",
        (_iso(criados_antes_de),),
    )
    return [Anexo(**dict(linha)) for linha in linhas]


def _caminho_portavel(caminho: str | PurePath) -> str:
    """Caminho relativo à pasta de dados, com `/` em qualquer sistema e sem sair da pasta."""
    texto = str(caminho).replace("\\", "/").strip()
    partes = texto.split("/")
    # Absoluto (`/x`, `C:/x`, `//servidor`), vazio ou com `..`/segmento vazio é recusado.
    if not texto or re.match(r"[A-Za-z]:", texto) or any(parte in ("", "..") for parte in partes):
        raise ValorInvalido("O caminho do anexo deve ser relativo à pasta de dados.")
    return texto


# --- vetores dos trechos (busca semântica, §2.5) ---


def listar_vetores(conexao: sqlite3.Connection) -> dict[str, bytes]:
    linhas = conexao.execute("SELECT chave, vetor FROM vetores_trechos")
    return {linha["chave"]: linha["vetor"] for linha in linhas}


def guardar_vetores(conexao: sqlite3.Connection, vetores: Mapping[str, bytes]) -> None:
    conexao.executemany(
        "INSERT OR REPLACE INTO vetores_trechos (chave, vetor) VALUES (?, ?)", vetores.items()
    )


def apagar_vetores(conexao: sqlite3.Connection, chaves: Iterable[str]) -> None:
    conexao.executemany("DELETE FROM vetores_trechos WHERE chave = ?", ((c,) for c in chaves))
