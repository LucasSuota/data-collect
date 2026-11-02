import pytest

from forms.formulas import TipoFormula, carregar_formula, inferir_tipo
from forms.models import FormulaInvalida, Posicao

N, DT, B, DU = (
    TipoFormula.NUMERO,
    TipoFormula.DATA,
    TipoFormula.BOOLEANO,
    TipoFormula.DURACAO,
)

# campos de exemplo: n1 e n2 numéricos, d1 e d2 datas, b1 e b2 sim/não
CAMPOS = {"n1": N, "n2": N, "d1": DT, "d2": DT, "b1": B, "b2": B}


def _tipo(texto: str, nao_utilizaveis: dict[str, str] | None = None) -> TipoFormula:
    return inferir_tipo(carregar_formula(texto), CAMPOS, nao_utilizaveis)


# --- combinações aceitas ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("n1 + n2", N),
        ("n1 - n2", N),
        ("n1 * n2", N),
        ("n1 / n2", N),
        ("n1 ** n2", N),
        ("-n1", N),
        ("1 + 2.5", N),
        ("pi * n1", N),
        ("d1 + dias(28)", DT),
        ("d1 - dias(1)", DT),
        ("d2 - d1", N),
        ("n1 == n2", B),
        ("n1 != n2", B),
        ("n1 < n2", B),
        ("n1 <= n2", B),
        ("n1 > n2", B),
        ("n1 >= n2", B),
        ("d1 == d2", B),
        ("d1 != d2", B),
        ("d1 < d2", B),
        ("d1 <= d2", B),
        ("d1 > d2", B),
        ("d1 >= d2", B),
        ("b1 == b2", B),
        ("b1 != b2", B),
        ("b1 and b2", B),
        ("b1 or b2 or b1", B),
        ("not b1", B),
        ("n1 > 1 and d1 < d2", B),
        ("True", B),
        ("soma(n1, n2, 3)", N),
        ("media(n1, n2)", N),
        ("min(n1, n2)", N),
        ("max(n1, n2)", N),
        ("se(n1 > n2, n1, n2)", N),
        ("se(b1, d1, d2)", DT),
        ("se(b1, b1, b2)", B),
        ("se(n1 > 0, d1 + dias(1), d2)", DT),
        ("d1 + dias(n1)", DT),
        ("d1 + dias(2.0)", DT),
        ("d1 + dias(-3)", DT),
    ],
)
def test_combinacao_aceita_infere_o_tipo(texto: str, esperado: TipoFormula):
    # act / assert
    assert _tipo(texto) is esperado


def test_calculado_que_depende_de_calculado_usa_o_tipo_inferido_dele():
    # arrange: o chamador informa o tipo já inferido de "dobro" (ordem topológica)
    tipos = CAMPOS | {"dobro": N, "prazo": DT}

    # act / assert
    assert inferir_tipo(carregar_formula("dobro * 2"), tipos) is N
    assert inferir_tipo(carregar_formula("prazo + dias(1)"), tipos) is DT
    assert inferir_tipo(carregar_formula("prazo > d1"), tipos) is B


def test_campo_compartilhado_entra_pelo_nome_com_o_tipo_da_origem():
    # arrange
    tipos = CAMPOS | {"ensaio__umidade": N, "ensaio__data": DT}

    # act / assert
    assert inferir_tipo(carregar_formula("ensaio__umidade * 2"), tipos) is N
    assert inferir_tipo(carregar_formula("ensaio__data + dias(2)"), tipos) is DT


# --- combinações rejeitadas ---


@pytest.mark.parametrize(
    "texto",
    [
        "d1 * 2",
        "d1 / d2",
        "d1 ** 2",
        "d1 + d2",
        "d1 + 1",
        "1 + d1",
        "dias(1) + d1",
        "dias(1) + dias(2)",
        "n1 - d1",
        "dias(1) - d1",
        "b1 + 1",
        "b1 * b2",
        "-d1",
        "-b1",
        "d1 >= 3",
        "n1 < d1",
        "b1 < b2",
        "b1 >= b2",
        "n1 == b1",
        "d1 == n1",
        "not n1",
        "not d1",
        "n1 and b1",
        "b1 and d1",
        "n1 or n2",
        "soma(d1, d2)",
        "media(b1, b2)",
        "min(n1, d1)",
        "max(d1)",
        "se(n1, 1, 2)",
        "se(d1, 1, 2)",
        "se(b1, n1, d1)",
        "se(b1, 1, b2)",
        "dias(d1)",
        "dias(b1)",
        "dias(1) == dias(1)",
        "dias(1) < dias(2)",
        "se(b1, dias(1), dias(2)) + d1 + d1",
    ],
)
def test_combinacao_rejeitada_levanta_formula_invalida_com_posicao(texto: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo(texto)

    # assert
    assert str(excecao.value)
    posicao = excecao.value.posicao
    assert posicao is not None
    assert 0 <= posicao.inicio < posicao.fim <= len(texto)


def test_mensagem_de_tipo_incompativel_diz_quais_tipos_se_encontraram():
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo("d1 * 2")

    # assert
    assert "data" in str(excecao.value) and "número" in str(excecao.value)
    assert excecao.value.posicao == Posicao(0, 6)


def test_posicao_aponta_o_trecho_com_problema_dentro_de_uma_formula_maior():
    # arrange
    texto = "n1 + (d1 * 2) + n2"

    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo(texto)

    # assert
    posicao = excecao.value.posicao
    assert texto[posicao.inicio : posicao.fim] == "d1 * 2"


def test_duracao_como_resultado_final_e_rejeitada():
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo("dias(28)")

    # assert
    assert "duração" in str(excecao.value)


def test_duracao_dentro_da_formula_e_aceita_desde_que_nao_seja_o_resultado():
    # act / assert
    assert _tipo("d1 + dias(28) > d2") is B


@pytest.mark.parametrize("texto", ["dias(2.5)", "dias(0.1)", "dias(-1.5)", "d1 + dias(1e-3)"])
def test_dias_com_constante_nao_inteira_e_rejeitado_ao_publicar(texto: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo(texto)

    # assert
    assert "inteiro" in str(excecao.value)


# --- nomes ---


def test_campo_inexistente_e_rejeitado_ao_publicar():
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo("n1 + fantasma")

    # assert
    assert "fantasma" in str(excecao.value) and "não existe" in str(excecao.value)
    assert excecao.value.posicao == Posicao(5, 13)


@pytest.mark.parametrize("tipo_do_campo", ["texto", "selecao", "secao", "localizacao", "foto"])
def test_campo_de_tipo_que_nao_entra_em_formula_e_rejeitado(tipo_do_campo: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        _tipo("n1 + obs", {"obs": tipo_do_campo})

    # assert
    assert "obs" in str(excecao.value) and tipo_do_campo in str(excecao.value)
    assert "fórmula" in str(excecao.value)


def test_nome_de_funcao_usado_como_variavel_e_rejeitado():
    # act / assert: `se` sem parênteses não é campo nem constante
    with pytest.raises(FormulaInvalida, match="não existe"):
        _tipo("se + 1")
