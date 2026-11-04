"""Importação do `forms.db` da versão anterior (AGENTS.md §2.4): preserva o histórico e
descarta as fotos, que saíram do produto."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forms import cli, servico
from forms.banco import Conexao

AGORA = datetime(2026, 12, 1, 9, 0, 0, tzinfo=UTC)

ESQUEMA_ANTIGO = """
CREATE TABLE pastas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
    nome_chave TEXT NOT NULL, pasta_pai_id INTEGER, criado_em TEXT NOT NULL);
CREATE TABLE formularios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE,
    criado_em TEXT NOT NULL, nome_chave TEXT, pasta_id INTEGER);
CREATE TABLE versoes_formulario (id INTEGER PRIMARY KEY AUTOINCREMENT, formulario_id INTEGER NOT NULL,
    numero INTEGER NOT NULL, definicao TEXT NOT NULL, publicada_em TEXT NOT NULL);
CREATE TABLE registros (id INTEGER PRIMARY KEY AUTOINCREMENT, formulario_id INTEGER NOT NULL,
    versao_id INTEGER NOT NULL, dados TEXT NOT NULL, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL);
CREATE TABLE dependencias_formulario (formulario_id INTEGER NOT NULL, depende_de_id INTEGER NOT NULL);
CREATE TABLE referencias_registro (registro_id INTEGER NOT NULL, campo_id TEXT NOT NULL, destino_id INTEGER NOT NULL);
"""

ENSAIO = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "compartilhado": True},
        {"id": "fotos", "tipo": "foto", "rotulo": "Fotos", "maximo": 3},
    ]
}
ENSAIO_V2 = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "compartilhado": True},
        {"id": "obs", "tipo": "texto", "rotulo": "Obs"},
    ]
}
PROCTOR = {
    "campos": [
        {
            "id": "e",
            "tipo": "referencia",
            "rotulo": "E",
            "formulario": "ensaio",
            "obrigatorio": True,
        },
        {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "e__umidade * 2"},
    ]
}


@pytest.fixture
def antigo(tmp_path: Path) -> Path:
    caminho = tmp_path / "forms.db"
    con = sqlite3.connect(caminho)
    con.executescript(ESQUEMA_ANTIGO)
    j = json.dumps
    con.execute("INSERT INTO pastas VALUES (1, 'Lab', 'lab', NULL, '2026-10-01T08:00:00+00:00')")
    con.execute("INSERT INTO pastas VALUES (2, 'Solos', 'solos', 1, '2026-10-01T08:05:00+00:00')")
    con.execute(
        "INSERT INTO formularios VALUES (1, 'ensaio', '2026-10-01T09:00:00+00:00', 'ensaio', 2)"
    )
    con.execute(
        "INSERT INTO formularios VALUES (2, 'proctor', '2026-10-02T09:00:00+00:00', 'proctor', NULL)"
    )
    con.execute(
        "INSERT INTO versoes_formulario VALUES (1, 1, 1, ?, '2026-10-01T09:00:00+00:00')",
        (j(ENSAIO),),
    )
    con.execute(
        "INSERT INTO versoes_formulario VALUES (2, 1, 2, ?, '2026-10-05T09:00:00+00:00')",
        (j(ENSAIO_V2),),
    )
    con.execute(
        "INSERT INTO versoes_formulario VALUES (3, 2, 1, ?, '2026-10-02T09:00:00+00:00')",
        (j(PROCTOR),),
    )
    con.execute(
        "INSERT INTO registros VALUES (10, 1, 1, ?, '2026-10-03T10:00:00+00:00', '2026-10-03T11:00:00+00:00')",
        (j({"umidade": "12.5", "fotos": [4, 5]}),),
    )
    con.execute(
        "INSERT INTO registros VALUES (11, 1, 2, ?, '2026-10-06T10:00:00+00:00', '2026-10-06T10:00:00+00:00')",
        (j({"umidade": "8", "obs": "x"}),),
    )
    con.execute(
        "INSERT INTO registros VALUES (20, 2, 3, ?, '2026-10-07T10:00:00+00:00', '2026-10-07T10:00:00+00:00')",
        (j({"e": 11, "dobro": {"valor": "16", "erro": None}}),),
    )
    con.execute("INSERT INTO dependencias_formulario VALUES (2, 1)")
    con.execute("INSERT INTO referencias_registro VALUES (20, 'e', 11)")
    con.commit()
    con.close()
    return caminho


def test_importa_pastas_formularios_versoes_registros_e_referencias(conexao: Conexao, antigo: Path):
    # act
    relatorio = servico.importar_sqlite(conexao, antigo, AGORA)

    # assert
    assert (relatorio.pastas, relatorio.formularios, relatorio.versoes) == (2, 2, 3)
    assert (relatorio.registros, relatorio.referencias) == (3, 1)
    formularios = {f.nome: f for f in servico.listar_formularios(conexao)}
    assert (
        formularios["ensaio"].versao_atual_numero == 2
        and formularios["proctor"].versao_atual_numero == 1
    )
    pastas = {p.nome: p for p in servico.listar_pastas(conexao)}
    assert pastas["Solos"].pasta_pai_id == pastas["Lab"].id
    assert formularios["ensaio"].pasta_id == pastas["Solos"].id


def test_ids_sao_remapeados_e_a_referencia_aponta_para_o_registro_certo(
    conexao: Conexao, antigo: Path
):
    # act
    servico.importar_sqlite(conexao, antigo, AGORA)

    # assert: o registro 20 (proctor) apontava para o 11 (v2 do ensaio)
    ensaio = servico.localizar_formulario(conexao, "ensaio").formulario.id
    origem = servico.listar_registros(conexao, ensaio, versao_id=None, limite=10).itens[0]
    proctor_id = servico.localizar_formulario(conexao, "proctor").formulario.id
    dependente = servico.listar_registros(conexao, proctor_id, limite=10).itens[0]
    assert origem.dados["obs"] == "x" and dependente.dados["e"] == origem.id


def test_datas_originais_sao_preservadas(conexao: Conexao, antigo: Path):
    # act
    servico.importar_sqlite(conexao, antigo, AGORA)

    # assert
    ensaio = servico.localizar_formulario(conexao, "ensaio")
    primeira_versao = servico.listar_versoes(conexao, ensaio.formulario.id)[0]
    assert ensaio.formulario.criado_em == "2026-10-01T09:00:00+00:00"
    assert primeira_versao.publicada_em == "2026-10-01T09:00:00+00:00"
    v1 = servico.listar_registros(
        conexao, ensaio.formulario.id, versao_id=primeira_versao.id
    ).itens[0]
    assert (v1.criado_em, v1.atualizado_em) == (
        "2026-10-03T10:00:00+00:00",
        "2026-10-03T11:00:00+00:00",
    )


def test_fotos_saem_das_definicoes_e_dos_valores_com_aviso(conexao: Conexao, antigo: Path):
    # act
    relatorio = servico.importar_sqlite(conexao, antigo, AGORA)

    # assert
    ensaio = servico.localizar_formulario(conexao, "ensaio").formulario.id
    v1 = servico.obter_versao(conexao, ensaio, servico.listar_versoes(conexao, ensaio)[0].id)
    assert [c.id for c in v1.definicao.campos] == ["umidade"]
    registro = servico.listar_registros(conexao, ensaio, versao_id=v1.id).itens[0]
    assert "fotos" not in registro.dados
    assert any("foto" in aviso for aviso in relatorio.avisos)
    assert any("fotos descartadas" in aviso for aviso in relatorio.avisos)


def test_cada_registro_importado_ganha_historico_com_o_motivo(conexao: Conexao, antigo: Path):
    # act
    servico.importar_sqlite(conexao, antigo, AGORA)

    # assert
    primeiro = servico.listar_registros(conexao, 1, limite=10).itens[0]
    entrada = servico.historico_do_registro(conexao, primeiro.id)[0][0]
    assert entrada.acao == "criado" and entrada.motivo == "importado do banco anterior"


def test_a_cascata_continua_funcionando_depois_da_importacao(conexao: Conexao, antigo: Path):
    # arrange
    servico.importar_sqlite(conexao, antigo, AGORA)
    ensaio = servico.localizar_formulario(conexao, "ensaio")
    origem = servico.listar_registros(conexao, ensaio.formulario.id, limite=10).itens[0]
    proctor = servico.localizar_formulario(conexao, "proctor").formulario.id

    # act
    servico.atualizar_registro(
        conexao, origem.id, {"umidade": "10", "obs": "y"}, AGORA, origem.revisao
    )

    # assert
    dependente = servico.listar_registros(conexao, proctor, limite=10).itens[0]
    assert dependente.dados["dobro"]["valor"] == "20"


def test_equipe_com_dados_recusa_a_importacao_e_nada_e_gravado(conexao: Conexao, antigo: Path):
    # arrange
    servico.criar_formulario(conexao, "ja-existe", {"campos": []}, AGORA)

    # act / assert
    with pytest.raises(servico.ImportacaoInvalida, match="equipe vazia"):
        servico.importar_sqlite(conexao, antigo, AGORA)
    assert [f.nome for f in servico.listar_formularios(conexao)] == ["ja-existe"]


def test_falha_no_meio_desfaz_tudo(conexao: Conexao, antigo: Path):
    # arrange: uma referência para um registro que não existe quebra a importação no fim
    con = sqlite3.connect(antigo)
    con.execute("INSERT INTO referencias_registro VALUES (20, 'x', 999)")
    con.commit()
    con.close()

    # act / assert
    with pytest.raises(KeyError):
        servico.importar_sqlite(conexao, antigo, AGORA)
    assert servico.listar_formularios(conexao) == [] and servico.listar_pastas(conexao) == []


def test_arquivo_que_nao_e_do_data_collect_e_recusado(conexao: Conexao, tmp_path: Path):
    # arrange
    estranho = tmp_path / "outro.db"
    con = sqlite3.connect(estranho)
    con.execute("CREATE TABLE clientes (id INTEGER)")
    con.commit()
    con.close()

    # act / assert
    with pytest.raises(servico.ImportacaoInvalida, match="faltam as tabelas"):
        servico.importar_sqlite(conexao, estranho, AGORA)
    with pytest.raises(servico.ImportacaoInvalida, match="não encontrado"):
        servico.importar_sqlite(conexao, tmp_path / "nao-existe.db", AGORA)


def test_a_importacao_abre_o_arquivo_so_para_leitura(conexao: Conexao, antigo: Path):
    # arrange
    antes = antigo.read_bytes()

    # act
    servico.importar_sqlite(conexao, antigo, AGORA)

    # assert
    assert antigo.read_bytes() == antes


def test_comando_da_cli_importa_e_mostra_o_relatorio_e_os_avisos(dsn, pessoa, antigo, capsys):
    # act
    codigo = cli.main(
        [
            "--dsn",
            dsn,
            "--equipe",
            str(pessoa["grupo_id"]),
            "--usuario",
            str(pessoa["usuario_id"]),
            "importar-sqlite",
            str(antigo),
        ],
        relogio=lambda: AGORA,
    )

    # assert
    saida = capsys.readouterr()
    assert codigo == 0 and "2 formulário(s)" in saida.out and "3 registro(s)" in saida.out
    assert "Aviso:" in saida.err


def test_comando_da_cli_em_equipe_com_dados_falha_com_mensagem(dsn, pessoa, antigo, capsys):
    # arrange
    conexao = servico.abrir_banco(dsn)
    conexao.definir_contexto(
        servico.contexto_da_pessoa(conexao, int(pessoa["usuario_id"]), int(pessoa["grupo_id"]))
    )
    servico.criar_formulario(conexao, "x", {"campos": []}, AGORA)

    # act
    codigo = cli.main(
        [
            "--dsn",
            dsn,
            "--equipe",
            str(pessoa["grupo_id"]),
            "--usuario",
            str(pessoa["usuario_id"]),
            "importar-sqlite",
            str(antigo),
        ],
        relogio=lambda: AGORA,
    )

    # assert
    assert codigo == 1 and "equipe vazia" in capsys.readouterr().err
    conexao.close()
