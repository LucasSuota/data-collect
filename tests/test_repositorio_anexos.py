import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath

import pytest

from forms.models import Campo, Definicao, NaoEncontrado, TipoCampo, ValorInvalido
from forms.repositorio import (
    abrir_conexao,
    apagar_anexo,
    criar_anexo,
    criar_formulario,
    desvincular_anexo,
    inserir_registro,
    inserir_versao,
    listar_anexos_do_registro,
    listar_anexos_orfaos,
    obter_anexo,
    vincular_anexo,
)

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEFINICAO = Definicao((Campo(id="fotos", tipo=TipoCampo.FOTO, rotulo="Fotos"),))


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def registro_id(conexao: sqlite3.Connection) -> int:
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    versao = inserir_versao(conexao, formulario.id, DEFINICAO, AGORA)
    return inserir_registro(conexao, formulario.id, versao.id, {}, AGORA).id


def _anexo(conexao, quando=AGORA, caminho="anexos/a.webp"):
    return criar_anexo(
        conexao, caminho, largura=640, altura=480, tamanho_bytes=61_000, agora=quando
    )


def test_criar_anexo_nasce_sem_registro_nem_campo(conexao):
    # act
    anexo = _anexo(conexao)

    # assert
    assert anexo.registro_id is None and anexo.campo_id is None
    assert (anexo.largura, anexo.altura, anexo.tamanho_bytes) == (640, 480, 61_000)
    assert anexo.criado_em == "2026-11-02T10:00:00+00:00"
    assert obter_anexo(conexao, anexo.id) == anexo


def test_ciclo_criar_vincular_desvincular_apagar(conexao, registro_id):
    # arrange
    anexo = _anexo(conexao)

    # act / assert: vincular
    vinculado = vincular_anexo(conexao, anexo.id, registro_id, "fotos")
    assert (vinculado.registro_id, vinculado.campo_id) == (registro_id, "fotos")
    assert listar_anexos_do_registro(conexao, registro_id) == [vinculado]

    # desvincular
    solto = desvincular_anexo(conexao, anexo.id)
    assert solto.registro_id is None and solto.campo_id is None
    assert listar_anexos_do_registro(conexao, registro_id) == []

    # apagar
    apagar_anexo(conexao, anexo.id)
    with pytest.raises(NaoEncontrado):
        obter_anexo(conexao, anexo.id)


def test_anexo_ja_vinculado_nao_pode_ser_vinculado_de_novo(conexao, registro_id):
    # arrange
    anexo = _anexo(conexao)
    vincular_anexo(conexao, anexo.id, registro_id, "fotos")

    # act / assert: um anexo não serve a dois campos (AGENTS.md §2.8)
    with pytest.raises(ValorInvalido, match="já está vinculado"):
        vincular_anexo(conexao, anexo.id, registro_id, "outra")


def test_vincular_anexo_inexistente_e_nao_encontrado(conexao, registro_id):
    # act / assert
    with pytest.raises(NaoEncontrado):
        vincular_anexo(conexao, 99, registro_id, "fotos")
    with pytest.raises(NaoEncontrado):
        apagar_anexo(conexao, 99)
    with pytest.raises(NaoEncontrado):
        desvincular_anexo(conexao, 99)


def test_vincular_a_registro_inexistente_e_recusado_pelo_banco(conexao):
    # arrange
    anexo = _anexo(conexao)

    # act / assert
    with pytest.raises(sqlite3.IntegrityError):
        vincular_anexo(conexao, anexo.id, 999, "fotos")


def test_listar_anexos_do_registro_so_traz_os_dele_na_ordem_de_criacao(conexao, registro_id):
    # arrange
    a, b, solto = (
        _anexo(conexao, caminho="anexos/1.webp"),
        _anexo(conexao, caminho="anexos/2.webp"),
        _anexo(conexao),
    )
    vincular_anexo(conexao, b.id, registro_id, "fotos")
    vincular_anexo(conexao, a.id, registro_id, "fotos")

    # act
    anexos = listar_anexos_do_registro(conexao, registro_id)

    # assert
    assert [x.id for x in anexos] == [a.id, b.id]
    assert solto.id not in [x.id for x in anexos]


# --- órfãos (relógio injetado) ---


def test_orfao_com_mais_de_24h_aparece_e_com_menos_nao(conexao):
    # arrange
    velho = _anexo(conexao, AGORA - timedelta(hours=25), "anexos/velho.webp")
    recente = _anexo(conexao, AGORA - timedelta(hours=23), "anexos/recente.webp")

    # act
    orfaos = listar_anexos_orfaos(conexao, criados_antes_de=AGORA - timedelta(hours=24))

    # assert
    assert [a.id for a in orfaos] == [velho.id]
    assert recente.id not in [a.id for a in orfaos]


def test_orfao_exatamente_no_limite_ainda_nao_e_removido(conexao):
    # arrange
    no_limite = _anexo(conexao, AGORA - timedelta(hours=24))

    # act / assert: "há mais de 24 h" é estritamente mais
    assert listar_anexos_orfaos(conexao, criados_antes_de=AGORA - timedelta(hours=24)) == []
    assert no_limite.id


def test_anexo_vinculado_a_um_registro_nunca_aparece_como_orfao(conexao, registro_id):
    # arrange
    antigo = _anexo(conexao, AGORA - timedelta(days=30))
    vincular_anexo(conexao, antigo.id, registro_id, "fotos")

    # act / assert
    assert listar_anexos_orfaos(conexao, criados_antes_de=AGORA) == []


def test_anexo_desvinculado_volta_a_poder_ser_orfao(conexao, registro_id):
    # arrange
    antigo = _anexo(conexao, AGORA - timedelta(days=30))
    vincular_anexo(conexao, antigo.id, registro_id, "fotos")
    desvincular_anexo(conexao, antigo.id)

    # act
    orfaos = listar_anexos_orfaos(conexao, criados_antes_de=AGORA)

    # assert
    assert [a.id for a in orfaos] == [antigo.id]


# --- caminho portátil ---


@pytest.mark.parametrize(
    ("entrada", "guardado"),
    [
        ("anexos/ab/cd.webp", "anexos/ab/cd.webp"),
        ("anexos\\ab\\cd.webp", "anexos/ab/cd.webp"),
        (Path("anexos") / "x.webp", "anexos/x.webp"),
        (PureWindowsPath("anexos", "x.webp"), "anexos/x.webp"),
    ],
)
def test_caminho_e_guardado_com_barra_normal_em_qualquer_sistema(conexao, entrada, guardado):
    # act
    anexo = _anexo(conexao, caminho=entrada)

    # assert
    assert anexo.caminho == guardado
    assert conexao.execute("SELECT caminho FROM anexos").fetchone()[0] == guardado


@pytest.mark.parametrize(
    "caminho",
    [
        "/etc/passwd",
        "C:\\Windows\\x.webp",
        "C:/x.webp",
        "../fora.webp",
        "anexos/../../fora.webp",
        "",
        "   ",
        "\\\\servidor\\x",
    ],
)
def test_caminho_absoluto_ou_que_sai_da_pasta_de_dados_e_recusado(conexao, caminho):
    # act / assert: sem path traversal (AGENTS.md §12)
    with pytest.raises(ValorInvalido):
        _anexo(conexao, caminho=caminho)
