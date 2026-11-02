import sqlite3
from pathlib import Path

import pytest

from forms.models import ErroDeDominio
from forms.repositorio import (
    MIGRACOES,
    VERSAO_ATUAL_DO_ESQUEMA,
    EsquemaMaisNovo,
    abrir_conexao,
    migrar,
)

# Esquema da versão 1, copiado literalmente. Quando o esquema mudar, este texto NÃO muda:
# ele representa o banco que o usuário já tem em disco, e o teste de atualização parte dele.
ESQUEMA_V1_LITERAL = """
CREATE TABLE formularios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    criado_em TEXT NOT NULL
);
CREATE TABLE versoes_formulario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    formulario_id INTEGER NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    definicao TEXT NOT NULL,
    publicada_em TEXT NOT NULL,
    UNIQUE (formulario_id, numero)
);
CREATE TABLE registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    formulario_id INTEGER NOT NULL REFERENCES formularios (id),
    versao_id INTEGER NOT NULL REFERENCES versoes_formulario (id),
    dados TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX registros_por_versao ON registros (formulario_id, versao_id);
CREATE TABLE dependencias_formulario (
    formulario_id INTEGER NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
    depende_de_id INTEGER NOT NULL REFERENCES formularios (id),
    PRIMARY KEY (formulario_id, depende_de_id)
);
CREATE TABLE referencias_registro (
    registro_id INTEGER NOT NULL REFERENCES registros (id) ON DELETE CASCADE,
    campo_id TEXT NOT NULL,
    destino_id INTEGER NOT NULL REFERENCES registros (id),
    PRIMARY KEY (registro_id, campo_id)
);
CREATE INDEX referencias_por_destino ON referencias_registro (destino_id);
CREATE TABLE anexos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id INTEGER REFERENCES registros (id),
    campo_id TEXT,
    caminho TEXT NOT NULL,
    largura INTEGER NOT NULL,
    altura INTEGER NOT NULL,
    tamanho_bytes INTEGER NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE INDEX anexos_por_registro ON anexos (registro_id);
"""


def _tabelas(conexao: sqlite3.Connection) -> set[str]:
    linhas = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )
    return {linha["name"] for linha in linhas}


def _colunas(conexao: sqlite3.Connection, tabela: str) -> list[str]:
    # nome da tabela vem de constante do teste, nunca de entrada externa
    return [linha["name"] for linha in conexao.execute(f"PRAGMA table_info({tabela})")]


def _versao_do_esquema(conexao: sqlite3.Connection) -> int:
    return conexao.execute("PRAGMA user_version").fetchone()[0]


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


def _inserir_formulario(conexao: sqlite3.Connection, nome: str = "ensaio") -> int:
    cursor = conexao.execute(
        "INSERT INTO formularios (nome, criado_em) VALUES (?, ?)", (nome, "2026-11-02T10:00:00")
    )
    return cursor.lastrowid


def _inserir_versao(conexao: sqlite3.Connection, formulario_id: int, numero: int = 1) -> int:
    cursor = conexao.execute(
        "INSERT INTO versoes_formulario (formulario_id, numero, definicao, publicada_em)"
        " VALUES (?, ?, ?, ?)",
        (formulario_id, numero, '{"campos": []}', "2026-11-02T10:00:00"),
    )
    return cursor.lastrowid


def _inserir_registro(conexao: sqlite3.Connection, formulario_id: int, versao_id: int) -> int:
    cursor = conexao.execute(
        "INSERT INTO registros (formulario_id, versao_id, dados, criado_em, atualizado_em)"
        " VALUES (?, ?, '{}', ?, ?)",
        (formulario_id, versao_id, "2026-11-02T10:00:00", "2026-11-02T10:00:00"),
    )
    return cursor.lastrowid


# --- banco novo ---


def test_banco_novo_sai_na_versao_atual_do_esquema(conexao: sqlite3.Connection):
    # assert
    assert _versao_do_esquema(conexao) == VERSAO_ATUAL_DO_ESQUEMA == len(MIGRACOES)


def test_banco_novo_tem_as_tabelas_do_modelo_de_dados(conexao: sqlite3.Connection):
    # assert
    assert _tabelas(conexao) == {
        "formularios",
        "versoes_formulario",
        "registros",
        "dependencias_formulario",
        "referencias_registro",
        "anexos",
    }


@pytest.mark.parametrize(
    ("tabela", "colunas"),
    [
        ("formularios", ["id", "nome", "criado_em", "nome_chave"]),
        ("versoes_formulario", ["id", "formulario_id", "numero", "definicao", "publicada_em"]),
        (
            "registros",
            ["id", "formulario_id", "versao_id", "dados", "criado_em", "atualizado_em"],
        ),
        ("dependencias_formulario", ["formulario_id", "depende_de_id"]),
        ("referencias_registro", ["registro_id", "campo_id", "destino_id"]),
        (
            "anexos",
            [
                "id",
                "registro_id",
                "campo_id",
                "caminho",
                "largura",
                "altura",
                "tamanho_bytes",
                "criado_em",
            ],
        ),
    ],
)
def test_colunas_de_cada_tabela_seguem_o_modelo_de_dados(
    conexao: sqlite3.Connection, tabela: str, colunas: list[str]
):
    # assert
    assert _colunas(conexao, tabela) == colunas


def test_abrir_conexao_liga_as_chaves_estrangeiras(conexao: sqlite3.Connection):
    # act
    ligado = conexao.execute("PRAGMA foreign_keys").fetchone()[0]

    # assert
    assert ligado == 1


def test_abrir_conexao_devolve_linhas_acessiveis_por_nome(conexao: sqlite3.Connection):
    # act
    linha = conexao.execute("SELECT 1 AS um").fetchone()

    # assert
    assert linha["um"] == 1


def test_abrir_conexao_em_arquivo_persiste_o_esquema(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    primeira = abrir_conexao(caminho)
    _inserir_formulario(primeira)
    primeira.commit()
    primeira.close()

    # act
    segunda = abrir_conexao(caminho)

    # assert
    assert _versao_do_esquema(segunda) == VERSAO_ATUAL_DO_ESQUEMA
    assert segunda.execute("SELECT COUNT(*) FROM formularios").fetchone()[0] == 1
    segunda.close()


def test_migrar_duas_vezes_nao_altera_nada(conexao: sqlite3.Connection):
    # act
    migrar(conexao)
    migrar(conexao)

    # assert
    assert _versao_do_esquema(conexao) == VERSAO_ATUAL_DO_ESQUEMA


# --- integridade (chaves estrangeiras e unicidade) ---


def test_nome_de_formulario_e_unico(conexao: sqlite3.Connection):
    # arrange
    _inserir_formulario(conexao, "ensaio")

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_formulario(conexao, "ensaio")


def test_numero_de_versao_e_unico_por_formulario(conexao: sqlite3.Connection):
    # arrange
    formulario_id = _inserir_formulario(conexao)
    _inserir_versao(conexao, formulario_id, numero=1)

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_versao(conexao, formulario_id, numero=1)


def test_registro_exige_formulario_e_versao_existentes(conexao: sqlite3.Connection):
    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_registro(conexao, formulario_id=99, versao_id=99)


def test_formulario_com_registros_nao_pode_ser_excluido(conexao: sqlite3.Connection):
    # arrange
    formulario_id = _inserir_formulario(conexao)
    versao_id = _inserir_versao(conexao, formulario_id)
    _inserir_registro(conexao, formulario_id, versao_id)

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute("DELETE FROM formularios WHERE id = ?", (formulario_id,))


def test_excluir_formulario_sem_registros_apaga_as_versoes(conexao: sqlite3.Connection):
    # arrange
    formulario_id = _inserir_formulario(conexao)
    _inserir_versao(conexao, formulario_id)

    # act
    conexao.execute("DELETE FROM formularios WHERE id = ?", (formulario_id,))

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM versoes_formulario").fetchone()[0] == 0


def test_registro_referenciado_por_outro_nao_pode_ser_excluido(conexao: sqlite3.Connection):
    # arrange
    formulario_id = _inserir_formulario(conexao)
    versao_id = _inserir_versao(conexao, formulario_id)
    origem = _inserir_registro(conexao, formulario_id, versao_id)
    dependente = _inserir_registro(conexao, formulario_id, versao_id)
    conexao.execute(
        "INSERT INTO referencias_registro (registro_id, campo_id, destino_id) VALUES (?, ?, ?)",
        (dependente, "ensaio", origem),
    )

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute("DELETE FROM registros WHERE id = ?", (origem,))


def test_excluir_registro_apaga_as_referencias_que_ele_mesmo_fazia(
    conexao: sqlite3.Connection,
):
    # arrange
    formulario_id = _inserir_formulario(conexao)
    versao_id = _inserir_versao(conexao, formulario_id)
    origem = _inserir_registro(conexao, formulario_id, versao_id)
    dependente = _inserir_registro(conexao, formulario_id, versao_id)
    conexao.execute(
        "INSERT INTO referencias_registro (registro_id, campo_id, destino_id) VALUES (?, ?, ?)",
        (dependente, "ensaio", origem),
    )

    # act
    conexao.execute("DELETE FROM registros WHERE id = ?", (dependente,))

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM referencias_registro").fetchone()[0] == 0


def test_formulario_de_origem_de_dependencia_nao_pode_ser_excluido(
    conexao: sqlite3.Connection,
):
    # arrange
    origem = _inserir_formulario(conexao, "ensaio")
    dependente = _inserir_formulario(conexao, "proctor")
    conexao.execute(
        "INSERT INTO dependencias_formulario (formulario_id, depende_de_id) VALUES (?, ?)",
        (dependente, origem),
    )

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute("DELETE FROM formularios WHERE id = ?", (origem,))


def test_anexo_nasce_sem_registro_e_exige_registro_existente_quando_vinculado(
    conexao: sqlite3.Connection,
):
    # act
    conexao.execute(
        "INSERT INTO anexos (caminho, largura, altura, tamanho_bytes, criado_em)"
        " VALUES (?, 1, 1, 1, ?)",
        ("anexos/a.webp", "2026-11-02T10:00:00"),
    )

    # assert
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute("UPDATE anexos SET registro_id = 99, campo_id = 'foto'")


# --- migração a partir de um esquema anterior ---


def _banco_na_versao_1_com_dados(caminho: Path) -> None:
    bruto = sqlite3.connect(caminho)
    bruto.executescript(ESQUEMA_V1_LITERAL)
    bruto.execute("INSERT INTO formularios (nome, criado_em) VALUES ('ensaio', '2026-11-02')")
    bruto.execute(
        "INSERT INTO versoes_formulario (formulario_id, numero, definicao, publicada_em)"
        " VALUES (1, 1, '{\"campos\": []}', '2026-11-02')"
    )
    bruto.execute(
        "INSERT INTO registros (formulario_id, versao_id, dados, criado_em, atualizado_em)"
        " VALUES (1, 1, '{\"a\": \"1\"}', '2026-11-02', '2026-11-02')"
    )
    bruto.execute("PRAGMA user_version = 1")
    bruto.commit()
    bruto.close()


def test_migracao_pendente_roda_sem_perder_dados(tmp_path: Path):
    # arrange: banco real da v1 e uma "v2" fictícia que só adiciona uma coluna
    caminho = tmp_path / "dados.db"
    _banco_na_versao_1_com_dados(caminho)

    def migracao_v2(conexao: sqlite3.Connection) -> None:
        conexao.execute("ALTER TABLE registros ADD COLUMN observacao TEXT")

    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row

    # act
    migrar(conexao, (MIGRACOES[0], migracao_v2))

    # assert
    assert _versao_do_esquema(conexao) == 2
    assert "observacao" in _colunas(conexao, "registros")
    registro = conexao.execute("SELECT dados, observacao FROM registros").fetchone()
    assert registro["dados"] == '{"a": "1"}'
    assert registro["observacao"] is None
    conexao.close()


def test_banco_da_v1_sem_migracoes_pendentes_fica_intacto(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    _banco_na_versao_1_com_dados(caminho)

    # act
    conexao = abrir_conexao(caminho)

    # assert
    assert _versao_do_esquema(conexao) == VERSAO_ATUAL_DO_ESQUEMA
    assert conexao.execute("SELECT dados FROM registros").fetchone()["dados"] == '{"a": "1"}'
    conexao.close()


def test_falha_numa_migracao_desfaz_tudo_e_mantem_a_versao(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    _banco_na_versao_1_com_dados(caminho)

    def migracao_quebrada(conexao: sqlite3.Connection) -> None:
        conexao.execute("ALTER TABLE registros ADD COLUMN observacao TEXT")
        conexao.execute("SELECT * FROM tabela_que_nao_existe")

    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row

    # act
    with pytest.raises(sqlite3.OperationalError):
        migrar(conexao, (MIGRACOES[0], migracao_quebrada))

    # assert: a coluna criada antes da falha também foi desfeita
    assert _versao_do_esquema(conexao) == 1
    assert "observacao" not in _colunas(conexao, "registros")
    conexao.close()


def test_banco_de_versao_mais_nova_que_o_app_e_recusado(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    bruto = sqlite3.connect(caminho)
    bruto.execute(f"PRAGMA user_version = {VERSAO_ATUAL_DO_ESQUEMA + 1}")
    bruto.close()

    # act
    with pytest.raises(EsquemaMaisNovo) as excecao:
        abrir_conexao(caminho)

    # assert
    assert isinstance(excecao.value, ErroDeDominio)
    assert "mais nova" in str(excecao.value)


def test_arquivo_nao_fica_travado_depois_de_recusar_banco_mais_novo(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    bruto = sqlite3.connect(caminho)
    bruto.execute(f"PRAGMA user_version = {VERSAO_ATUAL_DO_ESQUEMA + 1}")
    bruto.close()

    # act
    with pytest.raises(EsquemaMaisNovo):
        abrir_conexao(caminho)

    # assert: no Windows, uma conexão esquecida aberta impediria apagar o arquivo
    caminho.unlink()
    assert not caminho.exists()


def test_migracao_1_continua_igual_ao_esquema_publicado():
    # arrange: o esquema 1 já está no banco de quem instalou o app e nunca pode mudar
    de_referencia = sqlite3.connect(":memory:")
    de_referencia.executescript(ESQUEMA_V1_LITERAL)
    gerado = sqlite3.connect(":memory:")

    # act
    migrar(gerado, MIGRACOES[:1])

    # assert
    def definicoes(banco: sqlite3.Connection) -> set[tuple[str, str]]:
        linhas = banco.execute("SELECT name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
        return {(nome, " ".join(sql.split())) for nome, sql in linhas}

    assert definicoes(gerado) == definicoes(de_referencia)


# --- atualização real: esquema 1 (já em disco) -> esquema 2 ---


def test_atualizar_do_esquema_1_para_o_2_preenche_a_chave_do_nome_sem_perder_dados(tmp_path: Path):
    # arrange: banco real da v1, com dois formulários e um registro
    caminho = tmp_path / "dados.db"
    _banco_na_versao_1_com_dados(caminho)
    bruto = sqlite3.connect(caminho)
    bruto.execute("INSERT INTO formularios (nome, criado_em) VALUES ('  Inspeção ', '2026-11-02')")
    bruto.commit()
    bruto.close()

    # act
    conexao = abrir_conexao(caminho)

    # assert: dados intactos, versão atualizada e chave calculada para os nomes antigos
    assert _versao_do_esquema(conexao) == VERSAO_ATUAL_DO_ESQUEMA >= 2
    chaves = dict(conexao.execute("SELECT nome, nome_chave FROM formularios").fetchall())
    assert chaves == {"ensaio": "ensaio", "  Inspeção ": "inspeção"}
    assert conexao.execute("SELECT dados FROM registros").fetchone()["dados"] == '{"a": "1"}'
    conexao.close()


def test_depois_de_atualizar_a_unicidade_do_nome_vale_para_os_formularios_antigos(tmp_path: Path):
    # arrange
    caminho = tmp_path / "dados.db"
    _banco_na_versao_1_com_dados(caminho)
    conexao = abrir_conexao(caminho)

    # act / assert: "ENSAIO" já existia como "ensaio" antes da atualização
    with pytest.raises(sqlite3.IntegrityError):
        conexao.execute(
            "INSERT INTO formularios (nome, nome_chave, criado_em) VALUES ('ENSAIO', 'ensaio', 'x')"
        )
    conexao.close()
