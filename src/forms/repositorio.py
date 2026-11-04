"""Persistência em PostgreSQL: o módulo que fala SQL dos formulários e registros (AGENTS.md §5.1).

Sempre com parâmetros (`%s`), nunca f-string em SQL com dado externo (a regra `S608` do `ruff` e
um teste de varredura vigiam isso). A conexão entra por parâmetro em cada função; não há conexão
global. Toda consulta filtra por `grupo_id`, vindo do contexto da conexão (§2.13): o Row Level
Security do banco é a segunda barreira, nunca a única.

Estas funções não fazem commit: a transação é de quem chama (o serviço), para que várias
operações (por exemplo, a cascata de recálculo) entrem ou saiam juntas. O relógio entra por
parâmetro (`agora`, sempre em UTC); o repositório nunca lê a hora.
"""

import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from forms.banco import Conexao
from forms.models import (
    ConflitoDeRevisao,
    Definicao,
    DefinicaoInvalida,
    ErroDeCampo,
    Formulario,
    NaoEncontrado,
    Pasta,
    PastaInvalida,
    Registro,
    ValorInvalido,
    ValorJson,
    Versao,
)


def chave_do_nome(nome: str) -> str:
    """Forma comparável do nome: sem espaços nas pontas, sem diferenciar caixa nem a forma
    (composta ou decomposta) dos acentos. É calculada aqui e guardada numa coluna com índice
    único, para a unicidade não depender das regras de caixa do banco."""
    return unicodedata.normalize("NFC", nome.strip()).casefold()


def _iso(momento: datetime) -> str:
    if momento.tzinfo is None:
        raise ValorInvalido("O horário deve vir com fuso (UTC).")
    return momento.isoformat(timespec="seconds")


@dataclass(frozen=True)
class ResumoDeFormulario:
    id: int
    nome: str
    criado_em: str
    versao_atual_id: int | None
    versao_atual_numero: int | None
    pasta_id: int | None = None


@dataclass(frozen=True)
class ResumoDeVersao:
    id: int
    numero: int
    publicada_em: str


# --- formulários e versões ---


def criar_formulario(
    conexao: Conexao, nome: str, agora: datetime, pasta_id: int | None = None
) -> Formulario:
    nome = nome.strip()
    if not nome:
        raise DefinicaoInvalida((ErroDeCampo("nome", "O nome do formulário é obrigatório."),))
    chave = chave_do_nome(nome)
    repetido = conexao.execute(
        "SELECT 1 FROM formularios WHERE grupo_id = %s AND nome_chave = %s",
        (conexao.grupo_id, chave),
    ).fetchone()
    if repetido:
        raise DefinicaoInvalida((ErroDeCampo("nome", "Já existe um formulário com este nome."),))
    linha = conexao.execute(
        "INSERT INTO formularios (grupo_id, nome, nome_chave, criado_em, pasta_id)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (conexao.grupo_id, nome, chave, _iso(agora), pasta_id),
    ).fetchone()
    assert linha is not None  # INSERT ... RETURNING sempre devolve a linha criada
    return obter_formulario(conexao, linha["id"])


def obter_formulario(conexao: Conexao, formulario_id: int) -> Formulario:
    linha = conexao.execute(
        "SELECT id, nome, criado_em, pasta_id FROM formularios WHERE id = %s AND grupo_id = %s",
        (formulario_id, conexao.grupo_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Formulário {formulario_id} não encontrado.")
    return _formulario_da_linha(linha)


def obter_formulario_por_nome(conexao: Conexao, nome: str) -> Formulario | None:
    linha = conexao.execute(
        "SELECT id, nome, criado_em, pasta_id FROM formularios"
        " WHERE grupo_id = %s AND nome_chave = %s",
        (conexao.grupo_id, chave_do_nome(nome)),
    ).fetchone()
    return None if linha is None else _formulario_da_linha(linha)


def _formulario_da_linha(linha: Mapping[str, object]) -> Formulario:
    return Formulario(
        int(str(linha["id"])),
        str(linha["nome"]),
        str(linha["criado_em"]),
        None if linha["pasta_id"] is None else int(str(linha["pasta_id"])),
    )


def listar_formularios(conexao: Conexao) -> list[ResumoDeFormulario]:
    linhas = conexao.execute(
        """
        SELECT f.id, f.nome, f.criado_em, v.id AS versao_atual_id, v.numero AS versao_atual_numero,
               f.pasta_id
        FROM formularios f
        LEFT JOIN versoes_formulario v
            ON v.formulario_id = f.id
            AND v.numero = (SELECT MAX(numero) FROM versoes_formulario WHERE formulario_id = f.id)
        WHERE f.grupo_id = %s
        ORDER BY f.id
        """,
        (conexao.grupo_id,),
    )
    return [ResumoDeFormulario(**dict(linha)) for linha in linhas]


def mover_formulario(conexao: Conexao, formulario_id: int, pasta_id: int | None) -> None:
    """Só troca a pasta: versões, registros e dependências não se mexem."""
    cursor = conexao.execute(
        "UPDATE formularios SET pasta_id = %s WHERE id = %s AND grupo_id = %s",
        (pasta_id, formulario_id, conexao.grupo_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Formulário {formulario_id} não encontrado.")


# --- pastas ---

_MENSAGEM_NOME_REPETIDO = "Já existe uma pasta com este nome neste local."


def criar_pasta(conexao: Conexao, nome: str, pasta_pai_id: int | None, agora: datetime) -> Pasta:
    nome = _nome_da_pasta(nome)
    _conferir_nome_livre(conexao, nome, pasta_pai_id, ignorar_id=None)
    linha = conexao.execute(
        "INSERT INTO pastas (grupo_id, nome, nome_chave, pasta_pai_id, criado_em)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (conexao.grupo_id, nome, chave_do_nome(nome), pasta_pai_id, _iso(agora)),
    ).fetchone()
    assert linha is not None
    return obter_pasta(conexao, linha["id"])


def obter_pasta(conexao: Conexao, pasta_id: int) -> Pasta:
    linha = conexao.execute(
        "SELECT id, nome, pasta_pai_id, criado_em FROM pastas WHERE id = %s AND grupo_id = %s",
        (pasta_id, conexao.grupo_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Pasta {pasta_id} não encontrada.")
    return Pasta(**dict(linha))


def pasta_existe(conexao: Conexao, pasta_id: int) -> bool:
    return (
        conexao.execute(
            "SELECT 1 FROM pastas WHERE id = %s AND grupo_id = %s", (pasta_id, conexao.grupo_id)
        ).fetchone()
        is not None
    )


def listar_pastas(conexao: Conexao) -> list[Pasta]:
    linhas = conexao.execute(
        "SELECT id, nome, pasta_pai_id, criado_em FROM pastas WHERE grupo_id = %s ORDER BY id",
        (conexao.grupo_id,),
    )
    return [Pasta(**dict(linha)) for linha in linhas]


def atualizar_pasta(conexao: Conexao, pasta_id: int, nome: str, pasta_pai_id: int | None) -> Pasta:
    """Renomeia e/ou move. Quem chama já conferiu a existência do destino e o ciclo."""
    obter_pasta(conexao, pasta_id)
    nome = _nome_da_pasta(nome)
    _conferir_nome_livre(conexao, nome, pasta_pai_id, ignorar_id=pasta_id)
    conexao.execute(
        "UPDATE pastas SET nome = %s, nome_chave = %s, pasta_pai_id = %s"
        " WHERE id = %s AND grupo_id = %s",
        (nome, chave_do_nome(nome), pasta_pai_id, pasta_id, conexao.grupo_id),
    )
    return obter_pasta(conexao, pasta_id)


def excluir_pasta(conexao: Conexao, pasta_id: int) -> None:
    """O banco recusa (IntegrityError) se há subpasta ou formulário; quem chama confere antes."""
    cursor = conexao.execute(
        "DELETE FROM pastas WHERE id = %s AND grupo_id = %s", (pasta_id, conexao.grupo_id)
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Pasta {pasta_id} não encontrada.")


def pasta_esta_na_subarvore(conexao: Conexao, pasta_id: int, raiz_id: int) -> bool:
    """A `pasta_id` é a `raiz_id` ou está dentro dela (em qualquer profundidade)?

    Sobe pelos pais a partir de `pasta_id`: a árvore é acíclica, então a consulta termina.
    """
    linha = conexao.execute(
        """
        WITH RECURSIVE ancestrais (id) AS (
            SELECT %s::bigint
            UNION
            SELECT p.pasta_pai_id FROM pastas p JOIN ancestrais a ON p.id = a.id
            WHERE p.pasta_pai_id IS NOT NULL AND p.grupo_id = %s
        )
        SELECT 1 FROM ancestrais WHERE id = %s
        """,
        (pasta_id, conexao.grupo_id, raiz_id),
    ).fetchone()
    return linha is not None


def contar_subpastas(conexao: Conexao, pasta_id: int) -> int:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n FROM pastas WHERE pasta_pai_id = %s AND grupo_id = %s",
        (pasta_id, conexao.grupo_id),
    ).fetchone()
    return int(linha["n"]) if linha else 0


def contar_formularios_da_pasta(conexao: Conexao, pasta_id: int) -> int:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n FROM formularios WHERE pasta_id = %s AND grupo_id = %s",
        (pasta_id, conexao.grupo_id),
    ).fetchone()
    return int(linha["n"]) if linha else 0


def _nome_da_pasta(nome: str) -> str:
    nome = nome.strip()
    if not nome:
        raise PastaInvalida((ErroDeCampo("nome", "O nome da pasta é obrigatório."),))
    return nome


def _conferir_nome_livre(
    conexao: Conexao, nome: str, pasta_pai_id: int | None, ignorar_id: int | None
) -> None:
    repetida = conexao.execute(
        """
        SELECT 1 FROM pastas
        WHERE grupo_id = %s AND nome_chave = %s
            AND COALESCE(pasta_pai_id, 0) = COALESCE(%s::bigint, 0)
            AND (%s::bigint IS NULL OR id != %s::bigint)
        """,
        (conexao.grupo_id, chave_do_nome(nome), pasta_pai_id, ignorar_id, ignorar_id),
    ).fetchone()
    if repetida:
        raise PastaInvalida((ErroDeCampo("nome", _MENSAGEM_NOME_REPETIDO),))


def excluir_formulario(conexao: Conexao, formulario_id: int) -> None:
    """Apaga o formulário e suas versões. O banco recusa (IntegrityError) se houver registros
    ou dependentes; quem chama confere antes para devolver 409 com mensagem clara (§2.7)."""
    cursor = conexao.execute(
        "DELETE FROM formularios WHERE id = %s AND grupo_id = %s",
        (formulario_id, conexao.grupo_id),
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Formulário {formulario_id} não encontrado.")


def inserir_versao(
    conexao: Conexao, formulario_id: int, definicao: Definicao, agora: datetime
) -> Versao:
    """Publica a próxima versão (número anterior + 1). Não existe como alterar uma versão
    publicada: este módulo não tem `update` nem `delete` de versão (AGENTS.md §3.3)."""
    obter_formulario(conexao, formulario_id)
    linha = conexao.execute(
        """
        INSERT INTO versoes_formulario (grupo_id, formulario_id, numero, definicao, publicada_em)
        VALUES (%s, %s, (SELECT COALESCE(MAX(numero), 0) + 1 FROM versoes_formulario
                         WHERE formulario_id = %s), %s, %s)
        RETURNING id
        """,
        (
            conexao.grupo_id,
            formulario_id,
            formulario_id,
            Jsonb(definicao.para_json()),
            _iso(agora),
        ),
    ).fetchone()
    assert linha is not None
    return obter_versao(conexao, linha["id"])


def obter_versao(conexao: Conexao, versao_id: int, formulario_id: int | None = None) -> Versao:
    """Com `formulario_id`, só acha a versão se ela pertencer a esse formulário."""
    linha = conexao.execute(
        """
        SELECT id, formulario_id, numero, definicao, publicada_em FROM versoes_formulario
        WHERE id = %s AND grupo_id = %s AND (%s::bigint IS NULL OR formulario_id = %s::bigint)
        """,
        (versao_id, conexao.grupo_id, formulario_id, formulario_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Versão {versao_id} não encontrada.")
    return _versao_da_linha(linha)


def obter_versao_atual(conexao: Conexao, formulario_id: int) -> Versao:
    linha = conexao.execute(
        """
        SELECT id, formulario_id, numero, definicao, publicada_em FROM versoes_formulario
        WHERE formulario_id = %s AND grupo_id = %s ORDER BY numero DESC LIMIT 1
        """,
        (formulario_id, conexao.grupo_id),
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"O formulário {formulario_id} ainda não tem versão publicada.")
    return _versao_da_linha(linha)


def listar_versoes(conexao: Conexao, formulario_id: int) -> list[ResumoDeVersao]:
    linhas = conexao.execute(
        "SELECT id, numero, publicada_em FROM versoes_formulario"
        " WHERE formulario_id = %s AND grupo_id = %s ORDER BY numero",
        (formulario_id, conexao.grupo_id),
    )
    return [ResumoDeVersao(**dict(linha)) for linha in linhas]


def _versao_da_linha(linha: Mapping[str, object]) -> Versao:
    definicao = linha["definicao"]
    assert isinstance(definicao, dict)  # jsonb de objeto, escrito por `inserir_versao`
    return Versao(
        id=int(str(linha["id"])),
        formulario_id=int(str(linha["formulario_id"])),
        numero=int(str(linha["numero"])),
        definicao=Definicao.de_json(definicao),
        publicada_em=str(linha["publicada_em"]),
    )


# --- registros ---

_CAMPO_FILTRAVEL = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_COLUNAS_DO_REGISTRO = (
    "id, formulario_id, versao_id, dados, criado_em, atualizado_em, revisao,"
    " criado_por, atualizado_por"
)


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
    conexao: Conexao,
    formulario_id: int,
    versao_id: int,
    dados: Mapping[str, ValorJson],
    agora: datetime,
) -> Registro:
    momento = _iso(agora)
    linha = conexao.execute(
        "INSERT INTO registros (grupo_id, formulario_id, versao_id, dados, criado_em,"
        " atualizado_em, criado_por, atualizado_por) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        " RETURNING id",
        (
            conexao.grupo_id,
            formulario_id,
            versao_id,
            Jsonb(dados),
            momento,
            momento,
            conexao.usuario_id,
            conexao.usuario_id,
        ),
    ).fetchone()
    assert linha is not None
    return obter_registro(conexao, linha["id"])


def obter_registro(conexao: Conexao, registro_id: int, *, travar: bool = False) -> Registro:
    """Com `travar`, `SELECT ... FOR UPDATE`: a transação segura a linha até terminar (§2.14)."""
    consulta = f"SELECT {_COLUNAS_DO_REGISTRO} FROM registros WHERE id = %s AND grupo_id = %s"  # noqa: S608 - colunas fixas do módulo
    linha = conexao.execute(
        consulta + (" FOR UPDATE" if travar else ""), (registro_id, conexao.grupo_id)
    ).fetchone()
    if linha is None:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")
    return _registro_da_linha(linha)


def atualizar_registro(
    conexao: Conexao,
    registro_id: int,
    dados: Mapping[str, ValorJson],
    agora: datetime,
    *,
    revisao_esperada: int | None = None,
) -> Registro:
    """Substitui todos os dados (sem mesclar); a versão de origem e a criação não mudam.

    Com `revisao_esperada`, só grava se ninguém alterou o registro desde a leitura (§2.14).
    """
    cursor = conexao.execute(
        "UPDATE registros SET dados = %s, atualizado_em = %s, revisao = revisao + 1,"
        " atualizado_por = %s WHERE id = %s AND grupo_id = %s"
        " AND (%s::int IS NULL OR revisao = %s::int)",
        (
            Jsonb(dados),
            _iso(agora),
            conexao.usuario_id,
            registro_id,
            conexao.grupo_id,
            revisao_esperada,
            revisao_esperada,
        ),
    )
    if cursor.rowcount == 0:
        atual = obter_registro(conexao, registro_id)  # 404 se não existe
        raise ConflitoDeRevisao(
            f"O registro {registro_id} foi alterado por outra pessoa (revisão {atual.revisao})."
        )
    return obter_registro(conexao, registro_id)


def excluir_registro(conexao: Conexao, registro_id: int) -> None:
    cursor = conexao.execute(
        "DELETE FROM registros WHERE id = %s AND grupo_id = %s", (registro_id, conexao.grupo_id)
    )
    if cursor.rowcount == 0:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")


def contar_registros(conexao: Conexao, formulario_id: int) -> int:
    linha = conexao.execute(
        "SELECT COUNT(*) AS n FROM registros WHERE formulario_id = %s AND grupo_id = %s",
        (formulario_id, conexao.grupo_id),
    ).fetchone()
    return int(linha["n"]) if linha else 0


def listar_registros(
    conexao: Conexao,
    versao_id: int,
    *,
    limite: int,
    deslocamento: int,
    filtros: Sequence[FiltroDeIgualdade] = (),
    campos_permitidos: Collection[str] = frozenset(),
    criado_de: str | None = None,
    criado_ate: str | None = None,
    criado_por: int | None = None,
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
    onde, parametros = _condicoes_dos_registros(
        conexao, versao_id, filtros, campos_permitidos, criado_de, criado_ate, criado_por
    )
    # `onde` só tem fragmentos fixos de `_condicoes_dos_registros`; os valores são parâmetros.
    total = conexao.execute(
        f"SELECT COUNT(*) AS n FROM registros WHERE {onde}",  # noqa: S608
        parametros,
    ).fetchone()
    linhas = conexao.execute(
        f"SELECT {_COLUNAS_DO_REGISTRO} FROM registros"  # noqa: S608
        f" WHERE {onde} ORDER BY id DESC LIMIT %s OFFSET %s",
        [*parametros, limite, deslocamento],
    )
    return PaginaDeRegistros(
        tuple(_registro_da_linha(linha) for linha in linhas), int(total["n"]) if total else 0
    )


def contar_por_estado(
    conexao: Conexao,
    versao_id: int,
    campo_status: str,
    *,
    filtros: Sequence[FiltroDeIgualdade] = (),
    campos_permitidos: Collection[str] = frozenset(),
    criado_de: str | None = None,
    criado_ate: str | None = None,
    criado_por: int | None = None,
) -> dict[str, int]:
    """Contagem por estado do campo calculado booleano de status (§2.3): `conforme`,
    `nao_conforme`, `erro` e `aguardando`, com os mesmos filtros da listagem."""
    if not _CAMPO_FILTRAVEL.fullmatch(campo_status):
        raise ValorInvalido(f"Campo de status inválido: '{campo_status}'.")
    onde, parametros = _condicoes_dos_registros(
        conexao, versao_id, filtros, campos_permitidos, criado_de, criado_ate, criado_por
    )
    linhas = conexao.execute(
        """
        SELECT CASE
                   WHEN dados #>> %s::text[] IS NOT NULL THEN 'erro'
                   WHEN dados #>> %s::text[] = 'true' THEN 'conforme'
                   WHEN dados #>> %s::text[] = 'false' THEN 'nao_conforme'
                   ELSE 'aguardando'
               END AS estado, COUNT(*) AS n
        FROM registros WHERE """  # noqa: S608 - `onde` só tem fragmentos fixos
        + onde
        + " GROUP BY estado",
        [[campo_status, "erro"], [campo_status, "valor"], [campo_status, "valor"], *parametros],
    )
    contagem = {"conforme": 0, "nao_conforme": 0, "erro": 0, "aguardando": 0}
    for linha in linhas:
        contagem[str(linha["estado"])] = int(linha["n"])
    return contagem


def _condicoes_dos_registros(
    conexao: Conexao,
    versao_id: int,
    filtros: Sequence[FiltroDeIgualdade],
    campos_permitidos: Collection[str],
    criado_de: str | None,
    criado_ate: str | None,
    criado_por: int | None,
) -> tuple[str, list[object]]:
    condicoes = ["grupo_id = %s", "versao_id = %s"]
    parametros: list[object] = [conexao.grupo_id, versao_id]
    for filtro in filtros:
        condicoes.append("dados #>> %s::text[] = %s")
        parametros.extend(
            (_caminho_json(filtro, campos_permitidos), _valor_do_filtro(filtro.valor))
        )
    if criado_de is not None:
        condicoes.append("criado_em >= %s")
        parametros.append(criado_de)
    if criado_ate is not None:
        condicoes.append("criado_em <= %s")
        parametros.append(criado_ate)
    if criado_por is not None:
        condicoes.append("criado_por = %s")
        parametros.append(criado_por)
    return " AND ".join(condicoes), parametros


def _caminho_json(filtro: FiltroDeIgualdade, campos_permitidos: Collection[str]) -> list[str]:
    if filtro.campo not in campos_permitidos or not _CAMPO_FILTRAVEL.fullmatch(filtro.campo):
        raise ValorInvalido(f"Não é possível filtrar pelo campo '{filtro.campo}'.")
    return [filtro.campo, "valor"] if filtro.calculado else [filtro.campo]


def _valor_do_filtro(valor: str | bool) -> str:
    # `#>>` devolve o JSON como texto: `true`/`false` para booleano.
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return valor


def _registro_da_linha(linha: Mapping[str, object]) -> Registro:
    dados = linha["dados"]
    assert isinstance(dados, dict)  # jsonb de objeto, escrito por `inserir_registro`
    por = linha["criado_por"]
    atualizado = linha["atualizado_por"]
    return Registro(
        id=int(str(linha["id"])),
        formulario_id=int(str(linha["formulario_id"])),
        versao_id=int(str(linha["versao_id"])),
        dados=dados,
        criado_em=str(linha["criado_em"]),
        atualizado_em=str(linha["atualizado_em"]),
        revisao=int(str(linha["revisao"])),
        criado_por=None if por is None else int(str(por)),
        atualizado_por=None if atualizado is None else int(str(atualizado)),
    )


# --- histórico de alterações (§2.14) ---


@dataclass(frozen=True)
class EntradaDeHistorico:
    id: int
    registro_id: int
    usuario_id: int | None
    quando: str
    acao: str
    valores_anteriores: dict[str, ValorJson] | None
    motivo: str | None


def registrar_historico(
    conexao: Conexao,
    registro_id: int,
    acao: str,
    valores_anteriores: Mapping[str, ValorJson] | None,
    agora: datetime,
    motivo: str | None = None,
) -> None:
    conexao.execute(
        "INSERT INTO historico_registro (grupo_id, registro_id, usuario_id, quando, acao,"
        " valores_anteriores, motivo) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            conexao.grupo_id,
            registro_id,
            conexao.usuario_id,
            _iso(agora),
            acao,
            None if valores_anteriores is None else Jsonb(valores_anteriores),
            motivo,
        ),
    )


def listar_historico(conexao: Conexao, registro_id: int) -> list[EntradaDeHistorico]:
    linhas = conexao.execute(
        "SELECT id, registro_id, usuario_id, quando, acao, valores_anteriores, motivo"
        " FROM historico_registro WHERE registro_id = %s AND grupo_id = %s ORDER BY id DESC",
        (registro_id, conexao.grupo_id),
    )
    return [EntradaDeHistorico(**dict(linha)) for linha in linhas]


# --- relações entre formulários e entre registros (§2.7) ---

# Teto de segurança das consultas recursivas. O grafo é acíclico por construção (ciclo é
# rejeitado ao publicar), então isto só protege contra dado corrompido.
_PROFUNDIDADE_MAXIMA = 1000


def registrar_dependencias(
    conexao: Conexao, formulario_id: int, depende_de_ids: Collection[int]
) -> None:
    """Chamado ao publicar. O vínculo fica enquanto o formulário existir (versões antigas
    e seus registros ainda apontam para a origem)."""
    with conexao.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO dependencias_formulario (grupo_id, formulario_id, depende_de_id)"
            " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(conexao.grupo_id, formulario_id, origem) for origem in sorted(depende_de_ids)],
        )


def listar_dependencias(conexao: Conexao) -> list[tuple[int, int]]:
    """Todas as arestas `(formulario, depende_de)` da equipe, para o serviço detectar ciclo."""
    linhas = conexao.execute(
        "SELECT formulario_id, depende_de_id FROM dependencias_formulario WHERE grupo_id = %s"
        " ORDER BY formulario_id, depende_de_id",
        (conexao.grupo_id,),
    )
    return [(linha[0], linha[1]) for linha in linhas]


def formularios_dependentes(conexao: Conexao, formulario_id: int, *, transitivo: bool) -> list[int]:
    """Formulários que dependem deste, os mais próximos primeiro."""
    linhas = conexao.execute(
        """
        WITH RECURSIVE alcance(id, nivel) AS (
            SELECT formulario_id, 1 FROM dependencias_formulario
            WHERE depende_de_id = %s AND grupo_id = %s
            UNION ALL
            SELECT d.formulario_id, a.nivel + 1
            FROM dependencias_formulario d JOIN alcance a ON d.depende_de_id = a.id
            WHERE %s AND a.nivel < %s AND d.grupo_id = %s
        )
        SELECT id FROM alcance GROUP BY id ORDER BY MAX(nivel), id
        """,
        (formulario_id, conexao.grupo_id, transitivo, _PROFUNDIDADE_MAXIMA, conexao.grupo_id),
    )
    return [linha[0] for linha in linhas]


def substituir_referencias(
    conexao: Conexao, registro_id: int, referencias: Mapping[str, int]
) -> None:
    """Deixa as referências do registro exatamente como no último salvamento (campo -> destino)."""
    conexao.execute(
        "DELETE FROM referencias_registro WHERE registro_id = %s AND grupo_id = %s",
        (registro_id, conexao.grupo_id),
    )
    with conexao.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO referencias_registro (grupo_id, registro_id, campo_id, destino_id)"
            " VALUES (%s, %s, %s, %s)",
            [
                (conexao.grupo_id, registro_id, campo, destino)
                for campo, destino in referencias.items()
            ],
        )


def obter_referencias(conexao: Conexao, registro_id: int) -> dict[str, int]:
    linhas = conexao.execute(
        "SELECT campo_id, destino_id FROM referencias_registro"
        " WHERE registro_id = %s AND grupo_id = %s ORDER BY campo_id",
        (registro_id, conexao.grupo_id),
    )
    return {linha[0]: linha[1] for linha in linhas}


def registros_que_referenciam(conexao: Conexao, registro_id: int) -> list[int]:
    linhas = conexao.execute(
        "SELECT DISTINCT registro_id FROM referencias_registro"
        " WHERE destino_id = %s AND grupo_id = %s ORDER BY registro_id",
        (registro_id, conexao.grupo_id),
    )
    return [linha[0] for linha in linhas]


def registros_dependentes(conexao: Conexao, registro_id: int) -> list[int]:
    """Dependentes diretos e indiretos, em ordem de recálculo da cascata.

    Um registro só vem depois de todos aqueles dos quais depende: a ordenação usa o caminho
    *mais longo* até ele, para um destino alcançado por dois caminhos (diamante) ser
    recalculado só depois dos dois.
    """
    linhas = conexao.execute(
        """
        WITH RECURSIVE alcance(id, nivel) AS (
            SELECT registro_id, 1 FROM referencias_registro
            WHERE destino_id = %s AND grupo_id = %s
            UNION ALL
            SELECT r.registro_id, a.nivel + 1
            FROM referencias_registro r JOIN alcance a ON r.destino_id = a.id
            WHERE a.nivel < %s AND r.grupo_id = %s
        )
        SELECT id FROM alcance GROUP BY id ORDER BY MAX(nivel), id
        """,
        (registro_id, conexao.grupo_id, _PROFUNDIDADE_MAXIMA, conexao.grupo_id),
    )
    return [linha[0] for linha in linhas]


# --- vetores dos trechos de ajuda (busca semântica, §2.5) ---


def listar_vetores(conexao: Conexao) -> dict[str, bytes]:
    linhas = conexao.execute("SELECT chave, vetor FROM vetores_trechos")
    return {linha["chave"]: bytes(linha["vetor"]) for linha in linhas}


def guardar_vetores(conexao: Conexao, vetores: Mapping[str, bytes]) -> None:
    with conexao.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO vetores_trechos (chave, vetor) VALUES (%s, %s)"
            " ON CONFLICT (chave) DO UPDATE SET vetor = EXCLUDED.vetor",
            list(vetores.items()),
        )


def apagar_vetores(conexao: Conexao, chaves: Iterable[str]) -> None:
    with conexao.cursor() as cursor:
        cursor.executemany("DELETE FROM vetores_trechos WHERE chave = %s", [(c,) for c in chaves])


# --- busca global (§2.18) ---


def _como_padrao_like(termo: str) -> str:
    """O termo vira `%termo%` com `%`, `_` e `\\` escapados: o texto da pessoa é só dado."""
    escapado = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


def buscar_formularios_por_nome(conexao: Conexao, termo: str, limite: int) -> list[Formulario]:
    linhas = conexao.execute(
        "SELECT id, nome, criado_em, pasta_id FROM formularios"
        " WHERE grupo_id = %s AND nome ILIKE %s ORDER BY nome LIMIT %s",
        (conexao.grupo_id, _como_padrao_like(termo), limite),
    )
    return [_formulario_da_linha(linha) for linha in linhas]


def buscar_registros_por_texto(
    conexao: Conexao, termo: str, limite: int
) -> list[tuple[int, int, str]]:
    """(registro, formulário, nome do formulário) com o termo num campo `texto` ou `selecao`
    **da própria versão do registro**: número e data (guardados como texto) não entram."""
    linhas = conexao.execute(
        """
        SELECT r.id, r.formulario_id, f.nome FROM registros r
        JOIN formularios f ON f.id = r.formulario_id
        JOIN versoes_formulario v ON v.id = r.versao_id
        WHERE r.grupo_id = %s AND EXISTS (
            SELECT 1 FROM jsonb_each_text(r.dados) e,
                 jsonb_array_elements(v.definicao -> 'campos') c
            WHERE c ->> 'id' = e.key AND c ->> 'tipo' IN ('texto', 'selecao')
                AND e.value ILIKE %s
        )
        ORDER BY r.id DESC LIMIT %s
        """,
        (conexao.grupo_id, _como_padrao_like(termo), limite),
    )
    return [(linha[0], linha[1], linha[2]) for linha in linhas]


def registro_existe(conexao: Conexao, registro_id: int) -> tuple[int, str] | None:
    """(formulário, nome do formulário) do registro, se ele existe nesta equipe."""
    linha = conexao.execute(
        "SELECT r.formulario_id, f.nome FROM registros r JOIN formularios f"
        " ON f.id = r.formulario_id WHERE r.id = %s AND r.grupo_id = %s",
        (registro_id, conexao.grupo_id),
    ).fetchone()
    return None if linha is None else (linha[0], linha[1])


def registros_recentes(conexao: Conexao, limite: int) -> list[Registro]:
    linhas = conexao.execute(
        f"SELECT {_COLUNAS_DO_REGISTRO} FROM registros WHERE grupo_id = %s"  # noqa: S608
        " ORDER BY atualizado_em DESC, id DESC LIMIT %s",
        (conexao.grupo_id, limite),
    )
    return [_registro_da_linha(linha) for linha in linhas]
