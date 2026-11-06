import pytest

from forms.dominio.formulas import carregar_formula, nomes_usados, ordenar_calculados
from forms.dominio.models import CicloDeDependencia, DefinicaoInvalida


def _nomes(texto: str) -> tuple[str, ...]:
    return nomes_usados(carregar_formula(texto))


# --- nomes usados ---


def test_nomes_usados_vem_na_ordem_do_texto_sem_repetir():
    # act / assert
    assert _nomes("b + a * b - c") == ("b", "a", "c")


def test_nomes_usados_ignora_pi_e_nome_de_funcao():
    # act / assert
    assert _nomes("pi * se(x > 1, y, z)") == ("x", "y", "z")


def test_nomes_usados_inclui_campos_compartilhados():
    # act / assert
    assert _nomes("ensaio__umidade * 2") == ("ensaio__umidade",)


def test_formula_so_com_constantes_nao_usa_nomes():
    # act / assert
    assert _nomes("1 + 2") == ()


# --- ordem topológica ---


def test_cadeia_linear_sai_da_origem_para_o_destino():
    # arrange: c depende de b, que depende de a
    dependencias = {"c": ["b"], "b": ["a"], "a": []}

    # act / assert
    assert ordenar_calculados(dependencias) == ["a", "b", "c"]


def test_ramificacao_calcula_as_origens_antes_do_destino():
    # arrange
    dependencias = {"d": ["b", "c"], "b": ["a"], "c": ["a"], "a": []}

    # act
    ordem = ordenar_calculados(dependencias)

    # assert
    assert ordem.index("a") < ordem.index("b") < ordem.index("d")
    assert ordem.index("a") < ordem.index("c") < ordem.index("d")
    assert sorted(ordem) == ["a", "b", "c", "d"]


def test_ordem_e_estavel_para_a_mesma_definicao():
    # arrange
    dependencias = {"z": [], "y": [], "x": ["z"], "w": []}

    # act / assert
    assert ordenar_calculados(dependencias) == ordenar_calculados(dict(dependencias))
    assert ordenar_calculados(dependencias) == ["z", "y", "x", "w"]


def test_dependencia_que_nao_e_calculada_nao_entra_no_grafo():
    # arrange: "fck" é campo de entrada, não está no mapa de calculados
    dependencias = {"conforme": ["resistencia", "fck"], "resistencia": ["carga"]}

    # act / assert
    assert ordenar_calculados(dependencias) == ["resistencia", "conforme"]


def test_sem_campos_calculados_a_ordem_e_vazia():
    # act / assert
    assert ordenar_calculados({}) == []


@pytest.mark.parametrize(
    ("dependencias", "ciclo"),
    [
        ({"a": ["b"], "b": ["a"]}, ("a", "b", "a")),
        ({"a": ["b"], "b": ["c"], "c": ["a"]}, ("a", "b", "c", "a")),
        ({"a": ["a"]}, ("a", "a")),
        ({"x": [], "a": ["b"], "b": ["c"], "c": ["b"]}, ("b", "c", "b")),
    ],
)
def test_ciclo_e_rejeitado_citando_os_campos_envolvidos(
    dependencias: dict[str, list[str]], ciclo: tuple[str, ...]
):
    # act
    with pytest.raises(CicloDeDependencia) as excecao:
        ordenar_calculados(dependencias)

    # assert
    assert excecao.value.campos == ciclo
    for campo in set(ciclo):
        assert campo in str(excecao.value)


def test_ciclo_e_uma_definicao_invalida_localizada_na_formula():
    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        ordenar_calculados({"a": ["b"], "b": ["a"]})

    # assert
    assert [erro.campo for erro in excecao.value.erros] == ["a.formula"]


def test_cadeia_muito_longa_nao_estoura_a_pilha():
    # arrange
    dependencias = {f"c{i}": [f"c{i + 1}"] for i in range(5000)} | {"c5000": []}

    # act
    ordem = ordenar_calculados(dependencias)

    # assert
    assert ordem[0] == "c5000" and ordem[-1] == "c0"
