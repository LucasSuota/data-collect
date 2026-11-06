import ast
from pathlib import Path

import pytest

from forms.dominio import formulas
from forms.dominio.formulas import analisar_formula
from forms.dominio.models import FormulaInvalida, Posicao


@pytest.mark.parametrize(
    "texto",
    [
        "a + 1",
        "a - b * c / d",
        "a ** 2",
        "-a",
        "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)",
        "data_moldagem + dias(28)",
        "resistencia_mpa >= fck_mpa",
        "a == b",
        "a != b",
        "a < b",
        "a <= b",
        "a > b",
        "not conforme",
        "a > 1 and b < 2 or c",
        "True",
        "0.1 + 2",
        "se(d == 0, 0, x / d)",
        "media(a, b, c)",
        "soma(a, b) + min(a, b) + max(a, b)",
        "ensaio__umidade * 2",
    ],
)
def test_formula_valida_e_aceita(texto: str):
    # act
    arvore = analisar_formula(texto)

    # assert
    assert isinstance(arvore, ast.Expression)


@pytest.mark.parametrize(
    ("texto", "trecho_da_mensagem", "inicio", "fim"),
    [
        ("a + __import__('os')", "__import__", 4, 20),
        ("eval('1')", "eval", 0, 9),
        ("getattr(a, 'b')", "getattr", 0, 15),
        ("(lambda: 1)()", "lambda", 1, 10),
        ("().__class__", "atributo", 0, 12),
        ("a.b", "atributo", 0, 3),
        ("a.b()", "atributo", 0, 3),
        ("a[0]", "índice", 0, 4),
        ("lambda: 1", "lambda", 0, 9),
        ('f"{a}"', "f-string", 0, 6),
        ("[x for x in y]", "compreensão", 0, 14),
        ("{x for x in y}", "compreensão", 0, 14),
        ("(x for x in y)", "compreensão", 0, 14),
        ("a if b else c", "se(", 0, 13),
        ("(x := 1)", "atribuição", 1, 7),
        ("a // b", "operador", 0, 6),
        ("a % b", "operador", 0, 5),
        ("a @ b", "operador", 0, 5),
        ("+a", "operador", 0, 2),
        ("~a", "operador", 0, 2),
        ("a in b", "operador", 0, 6),
        ("a is b", "operador", 0, 6),
        ("'texto'", "texto", 0, 7),
        ("None", "constante", 0, 4),
        ("1j", "constante", 0, 2),
        ("[1, 2]", "construção", 0, 6),
        ("f(x=1)", "não permitida", 0, 6),
        ("se(*a)", "argumentos", 0, 6),
        ("1 < 2 < 3", "encadead", 0, 9),
    ],
)
def test_construcao_proibida_e_rejeitada_com_posicao(
    texto: str, trecho_da_mensagem: str, inicio: int, fim: int
):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    assert trecho_da_mensagem in str(excecao.value)
    assert excecao.value.posicao == Posicao(inicio=inicio, fim=fim)


def test_posicao_conta_caracteres_e_nao_bytes_utf8():
    # arrange: o `ast` mede em bytes, e o "ç" ocupa 2 bytes
    texto = "ç + x.y"

    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    assert excecao.value.posicao == Posicao(inicio=4, fim=7)
    assert texto[4:7] == "x.y"


def test_posicao_em_formula_com_quebra_de_linha():
    # arrange
    texto = "(a +\n  b.c)"

    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    posicao = excecao.value.posicao
    assert posicao is not None
    assert texto[posicao.inicio : posicao.fim] == "b.c"


@pytest.mark.parametrize("texto", ["a +", "a b", "((", "a + )", "1 +\n", "a = 1", "import os"])
def test_sintaxe_quebrada_vira_formula_invalida(texto: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    assert str(excecao.value)
    assert excecao.value.posicao is not None
    assert 0 <= excecao.value.posicao.inicio <= excecao.value.posicao.fim <= len(texto)


@pytest.mark.parametrize("texto", ["", "   ", "\n"])
def test_formula_vazia_e_rejeitada(texto: str):
    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    assert "vazia" in str(excecao.value)


def test_byte_nulo_vira_formula_invalida():
    # act / assert
    with pytest.raises(FormulaInvalida):
        analisar_formula("a\x00 + 1")


@pytest.mark.parametrize(
    "texto", ["(" * 5000 + "a" + ")" * 5000, "-" * 100_000 + "a", "a+" * 100_000 + "a"]
)
def test_formula_absurdamente_aninhada_nao_derruba_o_processo(texto: str):
    # act / assert
    with pytest.raises(FormulaInvalida):
        analisar_formula(texto)


def test_formulas_nao_usa_eval_exec_compile_nem_import_dinamico():
    # arrange
    arvore = ast.parse(Path(formulas.__file__).read_text(encoding="utf-8"))
    nomes_chamados = {
        no.func.id
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }

    # assert
    assert nomes_chamados.isdisjoint({"eval", "exec", "compile", "__import__"})


def test_formula_com_aninhamento_acima_do_limite_e_rejeitada_sem_estourar_a_pilha():
    # arrange: 200 somas encadeadas dão uma árvore de 200 níveis
    texto = "a" + " + a" * 200

    # act
    with pytest.raises(FormulaInvalida) as excecao:
        analisar_formula(texto)

    # assert
    assert "aninhadas" in str(excecao.value) and "soma(" in str(excecao.value)


def test_formula_longa_dentro_do_limite_e_aceita_e_avaliada():
    # arrange
    from decimal import Decimal

    from forms.dominio.formulas import avaliar, carregar_formula

    formula = carregar_formula("a" + " + a" * 100)

    # act / assert
    assert avaliar(formula, {"a": Decimal(1)}) == Decimal(101)
