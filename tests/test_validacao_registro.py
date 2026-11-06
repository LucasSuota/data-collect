from datetime import date
from decimal import Decimal

import pytest

from forms.dominio.models import Campo, Definicao, TipoCampo
from forms.dominio.tipos_campo import Localizacao
from forms.dominio.validacao import validar_registro

D = Decimal

DEFINICAO = Definicao(
    campos=(
        Campo(id="secao_1", tipo=TipoCampo.SECAO, rotulo="Dados"),
        Campo(id="fck", tipo=TipoCampo.NUMERO, rotulo="fck", obrigatorio=True),
        Campo(id="diametro", tipo=TipoCampo.NUMERO, rotulo="Diâmetro"),
        Campo(id="moldagem", tipo=TipoCampo.DATA, rotulo="Moldagem"),
        Campo(id="resultado", tipo=TipoCampo.SELECAO, rotulo="Resultado", opcoes=("OK", "Falha")),
        Campo(id="ensaiado", tipo=TipoCampo.SIM_NAO, rotulo="Ensaiado?"),
        Campo(id="obs", tipo=TipoCampo.TEXTO, rotulo="Observação"),
        Campo(id="local", tipo=TipoCampo.LOCALIZACAO, rotulo="Local"),
        Campo(id="ensaio", tipo=TipoCampo.REFERENCIA, rotulo="Ensaio", formulario="ensaio"),
        Campo(id="dobro", tipo=TipoCampo.CALCULADO, rotulo="Dobro", formula="fck * 2"),
    )
)


def _erros(dados: object, definicao: Definicao = DEFINICAO) -> dict[str, str]:
    resultado = validar_registro(definicao, dados)
    return {erro.campo: erro.mensagem for erro in resultado.erros}


def test_registro_valido_nao_tem_erros_e_expoe_valores_normalizados():
    # arrange
    dados = {
        "fck": 25.5,
        "diametro": "100",
        "moldagem": "2026-11-01",
        "resultado": "OK",
        "ensaiado": True,
        "obs": "ok",
        "local": {"latitude": "-23.550520", "longitude": "-46.633308"},
        "ensaio": 7,
    }

    # act
    resultado = validar_registro(DEFINICAO, dados)

    # assert
    assert resultado.erros == ()
    assert resultado.valores == {
        "fck": D("25.5"),
        "diametro": D("100"),
        "moldagem": date(2026, 11, 1),
        "resultado": "OK",
        "ensaiado": True,
        "obs": "ok",
        "local": Localizacao(D("-23.550520"), D("-46.633308")),
        "ensaio": 7,
    }


def test_numero_normalizado_e_decimal_pronto_para_o_calculo():
    # act
    resultado = validar_registro(DEFINICAO, {"fck": 0.1})

    # assert
    assert resultado.valores["fck"] == D("0.1")
    assert isinstance(resultado.valores["fck"], Decimal)


def test_campos_opcionais_ausentes_viram_none_nos_valores():
    # act
    resultado = validar_registro(DEFINICAO, {"fck": "25"})

    # assert
    assert resultado.erros == ()
    assert resultado.valores["diametro"] is None
    assert resultado.valores["moldagem"] is None


def test_valores_nao_incluem_calculado_nem_secao():
    # act
    resultado = validar_registro(DEFINICAO, {"fck": "25"})

    # assert
    assert "dobro" not in resultado.valores and "secao_1" not in resultado.valores


# --- obrigatório ---


@pytest.mark.parametrize("vazio", [None, ""])
def test_obrigatorio_vazio_e_erro_no_campo(vazio: object):
    # act
    erros = _erros({"fck": vazio})

    # assert
    assert erros == {"fck": "Campo obrigatório."}


def test_obrigatorio_ausente_e_erro_no_campo():
    # act / assert
    assert _erros({}) == {"fck": "Campo obrigatório."}


def test_obrigatorio_zero_nao_e_vazio():
    # act / assert
    assert _erros({"fck": 0}) == {}


def test_obrigatorio_false_nao_e_vazio():
    # arrange
    definicao = Definicao((Campo(id="ok", tipo=TipoCampo.SIM_NAO, rotulo="Ok", obrigatorio=True),))

    # act / assert
    assert _erros({"ok": False}, definicao) == {}


def test_obrigatorio_vale_para_o_par_da_localizacao():
    # arrange
    definicao = Definicao(
        (Campo(id="local", tipo=TipoCampo.LOCALIZACAO, rotulo="L", obrigatorio=True),)
    )

    # act
    erros = _erros({"local": {"latitude": "", "longitude": None}}, definicao)

    # assert
    assert erros == {"local": "Campo obrigatório."}


# --- tipo errado e opção inválida ---


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("diametro", "abc"),
        ("diametro", True),
        ("moldagem", "01/11/2026"),
        ("moldagem", "2026-02-30"),
        ("resultado", "Talvez"),
        ("resultado", 1),
        ("ensaiado", "sim"),
        ("obs", 5),
        ("ensaio", "7"),
        ("local", "-23,5 / -46,6"),
    ],
)
def test_valor_de_tipo_errado_ou_opcao_invalida_e_erro_no_campo(campo: str, valor: object):
    # act
    erros = _erros({"fck": "25", campo: valor})

    # assert
    assert list(erros) == [campo]


def test_opcao_invalida_cita_as_opcoes_validas():
    # act
    erros = _erros({"fck": "25", "resultado": "Talvez"})

    # assert
    assert "OK" in erros["resultado"] and "Falha" in erros["resultado"]


# --- chaves proibidas ---


def test_chave_de_campo_calculado_e_rejeitada_em_vez_de_ignorada():
    # act
    erros = _erros({"fck": "25", "dobro": "999"})

    # assert
    assert list(erros) == ["dobro"]
    assert "calculado" in erros["dobro"]


def test_chave_inexistente_e_rejeitada():
    # act
    erros = _erros({"fck": "25", "fantasma": 1})

    # assert
    assert list(erros) == ["fantasma"]
    assert "não existe" in erros["fantasma"]


def test_chave_de_secao_e_rejeitada():
    # act
    erros = _erros({"fck": "25", "secao_1": "x"})

    # assert
    assert list(erros) == ["secao_1"]
    assert "Seção" in erros["secao_1"]


# --- localização ---


def test_localizacao_fora_da_faixa_e_erro():
    # act
    erros = _erros({"fck": "25", "local": {"latitude": "91", "longitude": "0"}})

    # assert
    assert "latitude" in erros["local"]


def test_localizacao_incompleta_e_erro():
    # act
    erros = _erros({"fck": "25", "local": {"latitude": "10"}})

    # assert
    assert "latitude e longitude" in erros["local"]


def test_localizacao_vazia_e_aceita_quando_nao_obrigatoria():
    # act
    resultado = validar_registro(DEFINICAO, {"fck": "25", "local": {}})

    # assert
    assert resultado.erros == () and resultado.valores["local"] is None


# --- vários erros e forma dos dados ---


def test_devolve_todos_os_erros_de_uma_vez_localizados_por_id():
    # act
    erros = _erros(
        {"diametro": "abc", "moldagem": "x", "resultado": "Talvez", "dobro": 1, "fantasma": 2}
    )

    # assert
    assert set(erros) == {"fck", "diametro", "moldagem", "resultado", "dobro", "fantasma"}


@pytest.mark.parametrize("dados", [None, [], "texto", 5])
def test_dados_que_nao_sao_objeto_geram_erro_unico(dados: object):
    # act
    resultado = validar_registro(DEFINICAO, dados)

    # assert
    assert [e.campo for e in resultado.erros] == ["dados"]
    assert resultado.valores == {}


def test_validar_nao_altera_os_dados_recebidos():
    # arrange
    dados = {"fck": 25.5, "obs": "x"}
    copia = {"fck": 25.5, "obs": "x"}

    # act
    validar_registro(DEFINICAO, dados)

    # assert
    assert dados == copia


def test_registro_de_definicao_sem_campos_aceita_objeto_vazio():
    # act / assert
    assert validar_registro(Definicao(()), {}).erros == ()
    assert _erros({"x": 1}, Definicao(())) == {"x": "Este campo não existe na definição."}
