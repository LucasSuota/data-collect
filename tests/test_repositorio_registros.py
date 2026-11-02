import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from forms.models import Campo, Definicao, NaoEncontrado, TipoCampo, ValorInvalido
from forms.repositorio import (
    FiltroDeIgualdade,
    abrir_conexao,
    atualizar_registro,
    criar_formulario,
    excluir_registro,
    inserir_registro,
    inserir_versao,
    listar_registros,
    obter_registro,
)

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEFINICAO = Definicao((Campo(id="a", tipo=TipoCampo.TEXTO, rotulo="A"),))


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def versao(conexao: sqlite3.Connection):
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    return inserir_versao(conexao, formulario.id, DEFINICAO, AGORA)


def _inserir(conexao, versao, dados, quando=AGORA):
    return inserir_registro(conexao, versao.formulario_id, versao.id, dados, quando)


# --- inserir, obter, atualizar, excluir ---


def test_inserir_e_obter_registro_guarda_dados_em_json_e_a_versao_de_origem(conexao, versao):
    # act
    criado = _inserir(conexao, versao, {"a": "x", "n": "25.50"})

    # assert
    assert criado.versao_id == versao.id and criado.formulario_id == versao.formulario_id
    assert criado.dados == {"a": "x", "n": "25.50"}
    assert criado.criado_em == criado.atualizado_em == "2026-11-02T10:00:00+00:00"
    assert obter_registro(conexao, criado.id) == criado


def test_dados_com_calculado_preservam_a_estrutura_valor_e_erro(conexao, versao):
    # arrange
    dados = {
        "r": {"valor": "25.4", "erro": None},
        "c": {"valor": None, "erro": "Divisão por zero."},
    }

    # act / assert
    assert obter_registro(conexao, _inserir(conexao, versao, dados).id).dados == dados


def test_acentos_e_emojis_sobrevivem_ao_json(conexao, versao):
    # act
    criado = _inserir(conexao, versao, {"a": "Concreto armado — ensaio ✔ ção"})

    # assert
    assert obter_registro(conexao, criado.id).dados["a"] == "Concreto armado — ensaio ✔ ção"


def test_atualizar_substitui_os_dados_e_mantem_a_versao_e_a_criacao(conexao, versao):
    # arrange
    criado = _inserir(conexao, versao, {"a": "x", "b": "y"})
    depois = AGORA + timedelta(hours=2)

    # act
    atualizado = atualizar_registro(conexao, criado.id, {"a": "z"}, depois)

    # assert
    assert atualizado.dados == {"a": "z"}  # substitui, não mescla
    assert atualizado.versao_id == criado.versao_id
    assert atualizado.criado_em == criado.criado_em
    assert atualizado.atualizado_em == "2026-11-02T12:00:00+00:00"


def test_atualizar_ou_excluir_registro_inexistente_e_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        atualizar_registro(conexao, 99, {}, AGORA)
    with pytest.raises(NaoEncontrado):
        excluir_registro(conexao, 99)
    with pytest.raises(NaoEncontrado):
        obter_registro(conexao, 99)


def test_excluir_apaga_de_verdade(conexao, versao):
    # arrange
    criado = _inserir(conexao, versao, {"a": "x"})

    # act
    excluir_registro(conexao, criado.id)

    # assert
    with pytest.raises(NaoEncontrado):
        obter_registro(conexao, criado.id)


# --- listagem, paginação e total ---


def test_listagem_pagina_e_informa_o_total(conexao, versao):
    # arrange
    for i in range(5):
        _inserir(conexao, versao, {"a": str(i)})

    # act
    primeira = listar_registros(conexao, versao.id, limite=2, deslocamento=0)
    ultima = listar_registros(conexao, versao.id, limite=2, deslocamento=4)
    alem = listar_registros(conexao, versao.id, limite=2, deslocamento=10)

    # assert
    assert primeira.total == ultima.total == alem.total == 5
    assert len(primeira.itens) == 2 and len(ultima.itens) == 1 and alem.itens == ()


def test_listagem_mostra_o_mais_recente_primeiro_e_e_estavel(conexao, versao):
    # arrange
    ids = [_inserir(conexao, versao, {"a": str(i)}).id for i in range(3)]

    # act
    pagina = listar_registros(conexao, versao.id, limite=10, deslocamento=0)

    # assert
    assert [r.id for r in pagina.itens] == sorted(ids, reverse=True)


def test_listagem_so_traz_registros_da_versao_pedida(conexao, versao):
    # arrange
    segunda = inserir_versao(conexao, versao.formulario_id, DEFINICAO, AGORA)
    _inserir(conexao, versao, {"a": "antiga"})
    _inserir(conexao, segunda, {"a": "nova"})

    # act
    pagina = listar_registros(conexao, segunda.id, limite=10, deslocamento=0)

    # assert
    assert [r.dados["a"] for r in pagina.itens] == ["nova"] and pagina.total == 1


def test_listagem_vazia(conexao, versao):
    # act
    pagina = listar_registros(conexao, versao.id, limite=10, deslocamento=0)

    # assert
    assert pagina.itens == () and pagina.total == 0


@pytest.mark.parametrize(("limite", "deslocamento"), [(0, 0), (-1, 0), (10, -1)])
def test_limite_e_deslocamento_invalidos_sao_recusados(conexao, versao, limite, deslocamento):
    # act / assert
    with pytest.raises(ValorInvalido):
        listar_registros(conexao, versao.id, limite=limite, deslocamento=deslocamento)


# --- filtros ---

PERMITIDOS = frozenset({"resultado", "ensaiado", "obs", "conforme"})


def _carregar_variados(conexao, versao):
    _inserir(
        conexao,
        versao,
        {
            "resultado": "OK",
            "ensaiado": True,
            "obs": "alfa",
            "conforme": {"valor": True, "erro": None},
        },
    )
    _inserir(
        conexao,
        versao,
        {
            "resultado": "Falha",
            "ensaiado": False,
            "obs": "beta",
            "conforme": {"valor": False, "erro": None},
        },
    )
    _inserir(
        conexao,
        versao,
        {
            "resultado": "OK",
            "ensaiado": True,
            "obs": "alfa",
            "conforme": {"valor": None, "erro": "Divisão por zero."},
        },
    )


def _filtrar(conexao, versao, *filtros, **janela):
    return listar_registros(
        conexao,
        versao.id,
        limite=50,
        deslocamento=0,
        filtros=filtros,
        campos_permitidos=PERMITIDOS,
        **janela,
    )


def test_filtro_por_selecao(conexao, versao):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    pagina = _filtrar(conexao, versao, FiltroDeIgualdade("resultado", "OK"))

    # assert
    assert pagina.total == 2 and all(r.dados["resultado"] == "OK" for r in pagina.itens)


@pytest.mark.parametrize(("valor", "esperados"), [(True, 2), (False, 1)])
def test_filtro_por_sim_nao(conexao, versao, valor, esperados):
    # arrange
    _carregar_variados(conexao, versao)

    # act / assert
    assert _filtrar(conexao, versao, FiltroDeIgualdade("ensaiado", valor)).total == esperados


def test_filtro_por_texto(conexao, versao):
    # arrange
    _carregar_variados(conexao, versao)

    # act / assert
    assert _filtrar(conexao, versao, FiltroDeIgualdade("obs", "beta")).total == 1


@pytest.mark.parametrize(("valor", "esperados"), [(True, 1), (False, 1)])
def test_filtro_por_calculado_booleano_olha_o_valor_e_ignora_o_que_deu_erro(
    conexao, versao, valor, esperados
):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    pagina = _filtrar(conexao, versao, FiltroDeIgualdade("conforme", valor, calculado=True))

    # assert
    assert pagina.total == esperados


def test_filtros_combinam_com_e(conexao, versao):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    pagina = _filtrar(
        conexao, versao, FiltroDeIgualdade("resultado", "OK"), FiltroDeIgualdade("obs", "alfa")
    )

    # assert
    assert pagina.total == 2


def test_filtro_sem_correspondencia_devolve_vazio(conexao, versao):
    # arrange
    _carregar_variados(conexao, versao)

    # act / assert
    assert _filtrar(conexao, versao, FiltroDeIgualdade("obs", "inexistente")).total == 0


def test_total_respeita_o_filtro_e_nao_so_a_pagina(conexao, versao):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    pagina = listar_registros(
        conexao,
        versao.id,
        limite=1,
        deslocamento=0,
        filtros=[FiltroDeIgualdade("resultado", "OK")],
        campos_permitidos=PERMITIDOS,
    )

    # assert
    assert len(pagina.itens) == 1 and pagina.total == 2


def test_filtro_por_data_de_criacao_inclui_os_limites(conexao, versao):
    # arrange
    d1, d2, d3 = (AGORA + timedelta(days=i) for i in range(3))
    for quando in (d1, d2, d3):
        _inserir(conexao, versao, {"a": "x"}, quando)

    # act
    so_o_meio = _filtrar(conexao, versao, criado_de=d2.isoformat(), criado_ate=d2.isoformat())
    a_partir = _filtrar(conexao, versao, criado_de=d2.isoformat())
    ate = _filtrar(conexao, versao, criado_ate=d2.isoformat())

    # assert
    assert (so_o_meio.total, a_partir.total, ate.total) == (1, 2, 2)


# --- segurança: allowlist e parâmetros ---


@pytest.mark.parametrize(
    "campo",
    [
        "inexistente",
        "a') OR 1=1 --",
        'x"; DROP TABLE registros; --',
        "$.dados",
        "a.b",
        "resultado' --",
        "",
        "../x",
    ],
)
def test_nome_de_campo_fora_da_allowlist_e_recusado_antes_da_consulta(conexao, versao, campo):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    with pytest.raises(ValorInvalido):
        _filtrar(conexao, versao, FiltroDeIgualdade(campo, "OK"))

    # assert: nada foi executado nem apagado
    assert conexao.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == 3


def test_nome_na_allowlist_mas_com_formato_perigoso_tambem_e_recusado(conexao, versao):
    # arrange: mesmo que a allowlist de quem chama estivesse errada, o formato é conferido
    perigoso = "a') OR 1=1 --"

    # act / assert
    with pytest.raises(ValorInvalido):
        listar_registros(
            conexao,
            versao.id,
            limite=5,
            deslocamento=0,
            filtros=[FiltroDeIgualdade(perigoso, "x")],
            campos_permitidos=frozenset({perigoso}),
        )


@pytest.mark.parametrize(
    "valor", ["' OR '1'='1", "OK'; DROP TABLE registros; --", "%", "_", '" OR 1=1 --']
)
def test_valor_com_sql_e_so_um_valor_que_nao_casa(conexao, versao, valor):
    # arrange
    _carregar_variados(conexao, versao)

    # act
    pagina = _filtrar(conexao, versao, FiltroDeIgualdade("resultado", valor))

    # assert
    assert pagina.total == 0
    assert conexao.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == 3


def test_filtro_exige_a_allowlist(conexao, versao):
    # act / assert: sem `campos_permitidos`, qualquer filtro é recusado
    with pytest.raises(ValorInvalido):
        listar_registros(
            conexao, versao.id, limite=5, deslocamento=0, filtros=[FiltroDeIgualdade("a", "x")]
        )
