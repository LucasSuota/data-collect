"""Propriedades opcionais da definição: `exibicao` (§2.3, §5.2) e `ia: false` (§2.15)."""

import pytest

from forms.dominio.models import Campo, Definicao, TipoCampo
from forms.dominio.validacao import analisar_definicao

CAMPOS = [
    {"id": "carga", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
    {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "carga * 2"},
    {"id": "alto", "tipo": "calculado", "rotulo": "Alto?", "formula": "carga > 10"},
    {"id": "obs", "tipo": "texto", "rotulo": "Obs"},
    {"id": "secao", "tipo": "secao", "rotulo": "Seção"},
]


def _definicao(exibicao: object = None) -> dict:
    corpo: dict = {"campos": CAMPOS}
    if exibicao is not None:
        corpo["exibicao"] = exibicao
    return corpo


def _erros(exibicao: object) -> dict[str, str]:
    return {e.campo: e.mensagem for e in analisar_definicao(_definicao(exibicao)).erros}


def test_exibicao_valida_e_guardada_na_definicao():
    # act
    analise = analisar_definicao(
        _definicao({"destaque": "dobro", "status": "alto", "resumo": ["obs", "carga"]})
    )

    # assert
    assert analise.erros == ()
    assert analise.definicao is not None and analise.definicao.exibicao is not None
    assert analise.definicao.exibicao.destaque == "dobro"
    assert analise.definicao.exibicao.status == "alto"
    assert analise.definicao.exibicao.resumo == ("obs", "carga")


def test_exibicao_e_opcional():
    # act / assert
    analise = analisar_definicao(_definicao())
    assert analise.erros == () and analise.definicao is not None
    assert analise.definicao.exibicao is None


def test_exibicao_vai_e_volta_pelo_json_sem_perder_nada():
    # arrange
    corpo = _definicao({"destaque": "carga", "status": "alto", "resumo": ["obs"]})
    definicao = analisar_definicao(corpo).definicao
    assert definicao is not None

    # act
    de_volta = Definicao.de_json(definicao.para_json())

    # assert
    assert de_volta == definicao


@pytest.mark.parametrize(
    ("exibicao", "campo"),
    [
        ({"destaque": "obs"}, "exibicao.destaque"),  # texto não é numérico
        ({"destaque": "alto"}, "exibicao.destaque"),  # calculado booleano não é numérico
        ({"destaque": "fantasma"}, "exibicao.destaque"),
        ({"status": "dobro"}, "exibicao.status"),  # calculado numérico não é booleano
        ({"status": "carga"}, "exibicao.status"),  # entrada não é calculado
        ({"status": "fantasma"}, "exibicao.status"),
        ({"resumo": ["fantasma"]}, "exibicao.resumo"),
        ({"resumo": ["secao"]}, "exibicao.resumo"),  # seção é só visual
        ({"resumo": "obs"}, "exibicao.resumo"),
        ({"cor": "azul"}, "exibicao.cor"),  # propriedade desconhecida
    ],
)
def test_exibicao_invalida_e_rejeitada_com_o_erro_localizado(exibicao: dict, campo: str):
    # act / assert
    assert campo in _erros(exibicao)


def test_exibicao_que_nao_e_objeto_e_rejeitada():
    # act / assert
    assert "exibicao" in _erros(["x"])


def test_ia_false_e_aceito_em_qualquer_tipo_e_volta_na_definicao():
    # arrange
    corpo = {
        "campos": [
            {"id": "cpf", "tipo": "texto", "rotulo": "CPF", "ia": False},
            {"id": "n", "tipo": "numero", "rotulo": "N", "ia": True},
        ]
    }

    # act
    definicao = analisar_definicao(corpo).definicao

    # assert
    assert definicao is not None
    assert [c.ia for c in definicao.campos] == [False, True]
    # `ia: true` é o padrão e não aparece no JSON; só `false` é gravado
    assert definicao.para_json()["campos"][0]["ia"] is False
    assert "ia" not in definicao.para_json()["campos"][1]


def test_ia_deve_ser_booleano():
    # act
    erros = analisar_definicao(
        {"campos": [{"id": "a", "tipo": "texto", "rotulo": "A", "ia": "nao"}]}
    ).erros

    # assert
    assert [e.campo for e in erros] == ["a.ia"]


def test_campo_novo_tem_ia_ligada_por_padrao():
    # act / assert
    assert Campo(id="a", tipo=TipoCampo.TEXTO, rotulo="A").ia is True
