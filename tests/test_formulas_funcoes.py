from datetime import date, timedelta
from decimal import Decimal

import pytest

from forms.formulas import (
    CONSTANTES,
    FUNCOES,
    NOMES_RESERVADOS,
    TipoFormula,
    avaliar,
    carregar_formula,
)
from forms.models import ErroDeCalculo, FormulaInvalida

D = Decimal


def _avaliar(texto: str, **valores: object):
    return avaliar(carregar_formula(texto), valores)


# --- tabela única ---


def test_a_tabela_tem_exatamente_as_seis_funcoes_do_contrato():
    # assert
    assert set(FUNCOES) == {"se", "min", "max", "media", "soma", "dias"}


def test_toda_funcao_tem_assinatura_descricao_e_exemplo_que_funciona():
    # assert
    for nome, funcao in FUNCOES.items():
        assert funcao.nome == nome
        assert funcao.assinatura.startswith(f"{nome}(")
        assert funcao.descricao and funcao.exemplo.startswith(f"{nome}(")
        carregar_formula(funcao.exemplo)  # o exemplo da documentação é uma fórmula válida


def test_pi_e_a_unica_constante():
    # assert
    assert set(CONSTANTES) == {"pi"}
    assert CONSTANTES["pi"].tipo is TipoFormula.NUMERO


def test_nomes_reservados_saem_da_mesma_tabela():
    # assert
    assert NOMES_RESERVADOS == {"pi", "se", "min", "max", "media", "soma", "dias"}


# --- soma, media, min, max ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("soma(1, 2, 3)", D("6")),
        ("soma(5)", D("5")),
        ("media(2, 4, 9)", D("5")),
        ("media(7)", D("7")),
        ("media(1, 2)", D("1.5")),
        ("min(3, 1, 2)", D("1")),
        ("max(3, 1, 2)", D("3")),
        ("min(4)", D("4")),
        ("max(-1, -5)", D("-1")),
        ("soma(0.1, 0.2)", D("0.3")),
    ],
)
def test_funcoes_numericas_caminho_feliz(texto: str, esperado: Decimal):
    # act / assert
    assert _avaliar(texto) == esperado


@pytest.mark.parametrize("funcao", ["soma", "media", "min", "max"])
@pytest.mark.parametrize("posicao_do_vazio", [0, 1, 2])
def test_vazio_em_qualquer_argumento_gera_resultado_vazio(funcao: str, posicao_do_vazio: int):
    # arrange: nada é ignorado em silêncio (média parcial poderia gerar "conforme" falso)
    valores = {"a": D("1"), "b": D("2"), "c": D("3")}
    valores[("a", "b", "c")[posicao_do_vazio]] = None

    # act / assert
    assert _avaliar(f"{funcao}(a, b, c)", **valores) is None


@pytest.mark.parametrize("funcao", ["soma", "media", "min", "max"])
def test_funcao_numerica_sem_argumentos_e_rejeitada_ao_analisar(funcao: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        carregar_formula(f"{funcao}()")

    # assert
    assert funcao in str(excecao.value) and "argumento" in str(excecao.value)


# --- se ---


def test_se_escolhe_o_ramo_pela_condicao():
    # act / assert
    assert _avaliar("se(a > 1, 10, 20)", a=D("2")) == D("10")
    assert _avaliar("se(a > 1, 10, 20)", a=D("0")) == D("20")


def test_se_com_condicao_vazia_e_vazio():
    # act / assert
    assert _avaliar("se(a > 1, 10, 20)", a=None) is None


def test_se_com_ramo_escolhido_vazio_e_vazio():
    # act / assert
    assert _avaliar("se(True, a, 20)", a=None) is None


def test_se_avalia_so_o_ramo_escolhido():
    # arrange: o ramo não escolhido dividiria por zero
    # act / assert
    assert _avaliar("se(d == 0, 0, x / d)", d=D("0"), x=D("5")) == D("0")
    assert _avaliar("se(d == 0, 0, x / d)", d=D("2"), x=D("5")) == D("2.5")


def test_se_propaga_erro_do_ramo_escolhido():
    # act / assert
    with pytest.raises(ErroDeCalculo, match="zero"):
        _avaliar("se(True, 1 / 0, 2)")


def test_se_com_datas():
    # act / assert
    assert _avaliar("se(True, a, b)", a=date(2026, 1, 1), b=date(2027, 1, 1)) == date(2026, 1, 1)


def test_se_aninhado():
    # act / assert
    assert _avaliar("se(a > 10, 3, se(a > 5, 2, 1))", a=D("7")) == D("2")


@pytest.mark.parametrize("argumentos", ["", "True", "True, 1", "True, 1, 2, 3"])
def test_se_com_aridade_errada_e_rejeitado_ao_analisar(argumentos: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        carregar_formula(f"se({argumentos})")

    # assert
    assert "se" in str(excecao.value) and "3" in str(excecao.value)


# --- dias ---


def test_dias_com_valor_inteiro_de_campo():
    # act / assert
    assert _avaliar("dias(n)", n=D("28")) == timedelta(days=28)
    assert _avaliar("dias(n)", n=D("28.0")) == timedelta(days=28)


def test_dias_com_valor_nao_inteiro_vindo_de_campo_vira_erro_de_execucao():
    # act
    with pytest.raises(ErroDeCalculo) as excecao:
        _avaliar("dias(n)", n=D("2.5"))

    # assert
    assert "inteiro" in str(excecao.value)


def test_dias_com_vazio_e_vazio():
    # act / assert
    assert _avaliar("dias(n)", n=None) is None


@pytest.mark.parametrize("argumentos", ["", "1, 2"])
def test_dias_com_aridade_errada_e_rejeitado_ao_analisar(argumentos: str):
    # act / assert
    with pytest.raises(FormulaInvalida, match="dias"):
        carregar_formula(f"dias({argumentos})")


# --- outras funções e pi ---


@pytest.mark.parametrize("texto", ["raiz(4)", "round(1.5)", "abs(-1)", "len(a)", "print(1)"])
def test_qualquer_outra_funcao_gera_erro_claro(texto: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        carregar_formula(texto)

    # assert
    assert "não permitida" in str(excecao.value)


def test_pi_com_parenteses_explica_que_e_constante():
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        carregar_formula("pi()")

    # assert
    assert "constante" in str(excecao.value)
