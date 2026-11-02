from datetime import date, timedelta
from decimal import Decimal

import pytest

from forms.formulas import PI, avaliar, carregar_formula
from forms.models import ErroDeCalculo

D = Decimal


def _avaliar(texto: str, **valores: object):
    return avaliar(carregar_formula(texto), valores)


# --- aritmética ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1 + 2", D("3")),
        ("5 - 7", D("-2")),
        ("3 * 4", D("12")),
        ("10 / 4", D("2.5")),
        ("2 ** 10", D("1024")),
        ("2 ** 0.5 * 2 ** 0.5 > 1.99", True),
        ("-5 + 2", D("-3")),
        ("-(2 + 3)", D("-5")),
        ("2 + 3 * 4", D("14")),
        ("(2 + 3) * 4", D("20")),
        ("2 ** 3 ** 2", D("512")),
    ],
)
def test_operadores_aritmeticos(texto: str, esperado: object):
    # act / assert
    assert _avaliar(texto) == esperado


def test_resultado_e_decimal_e_nao_float():
    # act
    resultado = _avaliar("0.1 + 0.2")

    # assert
    assert isinstance(resultado, Decimal)
    assert resultado == D("0.3")  # com float seria 0.30000000000000004


def test_constante_decimal_vem_do_texto_e_nao_do_float():
    # act / assert: 0.1 + 0.2 em float não é 0.3; aqui tem de ser exato
    assert _avaliar("0.1 * 3") == D("0.3")
    assert _avaliar("1.10 + 2.20") == D("3.30")


def test_constante_com_expoente_e_aceita():
    # act / assert
    assert _avaliar("1e3 + 1") == D("1001")


def test_campo_numerico_entra_com_o_valor_decimal_informado():
    # act / assert
    assert _avaliar("a * b", a=D("2.5"), b=D("4")) == D("10.0")


def test_pi_tem_28_digitos_significativos():
    # act / assert
    assert _avaliar("pi") == PI
    assert len(PI.as_tuple().digits) == 28
    assert str(PI).startswith("3.14159265358979323846264338")


def test_precisao_do_calculo_e_fixa_em_28_digitos():
    # act
    resultado = _avaliar("1 / 3")

    # assert
    assert resultado == D("0.3333333333333333333333333333")


# --- comparações e booleanos ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2 == 2", True),
        ("2 == 3", False),
        ("2 != 3", True),
        ("2 < 3", True),
        ("3 < 3", False),
        ("3 <= 3", True),
        ("4 > 3", True),
        ("3 > 3", False),
        ("3 >= 3", True),
        ("1.0 == 1", True),
    ],
)
def test_comparacoes_entre_numeros(texto: str, esperado: bool):
    # act / assert
    assert _avaliar(texto) is esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("True and True", True),
        ("True and False", False),
        ("False or True", True),
        ("False or False", False),
        ("not True", False),
        ("not False", True),
        ("True == True", True),
        ("True != False", True),
        ("1 < 2 and 2 < 3", True),
        ("1 > 2 or 2 > 3", False),
    ],
)
def test_operadores_booleanos(texto: str, esperado: bool):
    # act / assert
    assert _avaliar(texto) is esperado


def test_and_com_varios_operandos():
    # act / assert
    assert _avaliar("a and b and c", a=True, b=True, c=False) is False
    assert _avaliar("a or b or c", a=False, b=False, c=True) is True


# --- datas ---


def test_data_mais_duracao():
    # act / assert
    assert _avaliar("d + dias(28)", d=date(2026, 11, 1)) == date(2026, 11, 29)


def test_data_menos_duracao():
    # act / assert
    assert _avaliar("d - dias(1)", d=date(2026, 3, 1)) == date(2026, 2, 28)


def test_data_menos_data_da_o_numero_de_dias_em_decimal():
    # act
    resultado = _avaliar("b - a", a=date(2026, 11, 1), b=date(2026, 11, 29))

    # assert
    assert resultado == D("28")
    assert isinstance(resultado, Decimal)


def test_data_menos_data_pode_ser_negativa():
    # act / assert
    assert _avaliar("a - b", a=date(2026, 11, 1), b=date(2026, 11, 29)) == D("-28")


def test_comparacao_entre_datas():
    # act / assert
    assert _avaliar("a < b", a=date(2026, 1, 1), b=date(2026, 1, 2)) is True
    assert _avaliar("a >= b", a=date(2026, 1, 1), b=date(2026, 1, 2)) is False
    assert _avaliar("a == b", a=date(2026, 1, 1), b=date(2026, 1, 1)) is True


def test_dias_devolve_duracao():
    # act / assert
    assert _avaliar("dias(3)") == timedelta(days=3)


# --- vazio propaga ---


@pytest.mark.parametrize(
    "texto",
    ["a + b", "a - b", "a * b", "a / b", "a ** b", "a == b", "a != b", "a < b", "a >= b"],
)
@pytest.mark.parametrize("vazio_em", ["a", "b", "ambos"])
def test_vazio_em_qualquer_posicao_gera_resultado_vazio(texto: str, vazio_em: str):
    # arrange
    valores = {"a": D("2"), "b": D("3")}
    for nome in ("a", "b") if vazio_em == "ambos" else (vazio_em,):
        valores[nome] = None

    # act / assert
    assert _avaliar(texto, **valores) is None


def test_menos_unario_de_vazio_e_vazio():
    # act / assert
    assert _avaliar("-a", a=None) is None


@pytest.mark.parametrize("texto", ["a and b", "a or b"])
def test_vazio_propaga_em_and_e_or_mesmo_com_o_outro_operando_decidindo(texto: str):
    # arrange: `False and vazio` poderia ser False, mas o contrato é nada ignorado em silêncio
    # act / assert
    assert _avaliar(texto, a=False, b=None) is None
    assert _avaliar(texto, a=True, b=None) is None
    assert _avaliar(texto, a=None, b=True) is None


def test_not_de_vazio_e_vazio():
    # act / assert
    assert _avaliar("not a", a=None) is None


def test_vazio_em_data_propaga():
    # act / assert
    assert _avaliar("d + dias(1)", d=None) is None
    assert _avaliar("b - a", a=None, b=date(2026, 1, 1)) is None


def test_campo_ausente_e_tratado_como_vazio():
    # act / assert
    assert _avaliar("a + b", a=D("1")) is None


def test_vazio_se_propaga_ate_o_resultado_final():
    # act / assert
    assert _avaliar("(a + 1) * 2 > 3", a=None) is None


# --- erros de execução ---


@pytest.mark.parametrize("texto", ["1 / 0", "a / b", "10 / (a - a)"])
def test_divisao_por_zero_levanta_erro_de_calculo_em_portugues(texto: str):
    # act
    with pytest.raises(ErroDeCalculo) as excecao:
        _avaliar(texto, a=D("1"), b=D("0"))

    # assert
    assert "zero" in str(excecao.value).lower()


def test_zero_dividido_por_zero_tambem_e_erro_de_divisao():
    # act
    with pytest.raises(ErroDeCalculo, match="zero"):
        _avaliar("0 / 0")


def test_zero_elevado_a_potencia_negativa_e_divisao_por_zero():
    # act
    with pytest.raises(ErroDeCalculo, match="zero"):
        _avaliar("0 ** -1")


def test_potencia_gigante_vira_erro_e_nao_trava():
    # act
    with pytest.raises(ErroDeCalculo, match="grande demais"):
        _avaliar("9 ** 9 ** 9 ** 9")


def test_raiz_de_numero_negativo_vira_erro():
    # act
    with pytest.raises(ErroDeCalculo, match="inválida"):
        _avaliar("(-8) ** 0.5")


def test_data_fora_do_intervalo_vira_erro():
    # act
    with pytest.raises(ErroDeCalculo, match="intervalo"):
        _avaliar("d + dias(3000000)", d=date(2026, 1, 1))


def test_dias_enorme_vira_erro():
    # act
    with pytest.raises(ErroDeCalculo, match="intervalo"):
        _avaliar("dias(a)", a=D("1e30"))


def test_avaliar_nao_altera_o_contexto_decimal_do_chamador():
    # arrange
    from decimal import getcontext

    precisao_antes = getcontext().prec
    getcontext().prec = 5

    try:
        # act
        _avaliar("1 / 3")

        # assert
        assert getcontext().prec == 5
    finally:
        getcontext().prec = precisao_antes
