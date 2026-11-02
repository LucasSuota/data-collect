import pytest

from forms.formulas import TipoFormula
from forms.models import DefinicaoInvalida, Posicao, TipoCampo
from forms.validacao import (
    CampoCompartilhado,
    analisar_definicao,
    exigir_definicao_valida,
    validar_definicao,
)

CORPO_DE_PROVA = {
    "campos": [
        {"id": "fck_mpa", "tipo": "numero", "rotulo": "fck", "unidade": "MPa", "obrigatorio": True},
        {"id": "diametro_mm", "tipo": "numero", "rotulo": "Diâmetro", "unidade": "mm"},
        {"id": "data_moldagem", "tipo": "data", "rotulo": "Data de moldagem"},
        {"id": "carga_kn", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
        {
            "id": "ruptura_28d",
            "tipo": "calculado",
            "rotulo": "Ruptura aos 28 dias",
            "formula": "data_moldagem + dias(28)",
        },
        {
            "id": "resistencia_mpa",
            "tipo": "calculado",
            "rotulo": "Resistência",
            "unidade": "MPa",
            "casas_decimais": 1,
            "formula": "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)",
        },
        {
            "id": "conforme",
            "tipo": "calculado",
            "rotulo": "Conforme?",
            "formula": "resistencia_mpa >= fck_mpa",
        },
    ]
}

ORIGENS = {
    "ensaio": {
        "umidade": CampoCompartilhado(TipoCampo.NUMERO, TipoFormula.NUMERO),
        "data": CampoCompartilhado(TipoCampo.DATA, TipoFormula.DATA),
        "operador": CampoCompartilhado(TipoCampo.TEXTO, None),
    }
}


def _definicao(*campos: dict[str, object]) -> dict[str, object]:
    return {"campos": list(campos)}


def _erros(definicao: object, origens=None) -> list[tuple[str, str]]:
    return [(e.campo, e.mensagem) for e in validar_definicao(definicao, origens)]


def _campos_com_erro(definicao: object, origens=None) -> list[str]:
    return [campo for campo, _ in _erros(definicao, origens)]


# --- definição válida ---


def test_definicao_valida_devolve_lista_vazia():
    # act / assert
    assert validar_definicao(CORPO_DE_PROVA) == ()


def test_definicao_valida_vira_dataclasses_e_expoe_os_tipos_inferidos():
    # act
    analise = analisar_definicao(CORPO_DE_PROVA)

    # assert
    assert analise.erros == ()
    assert [c.id for c in analise.definicao.campos][:2] == ["fck_mpa", "diametro_mm"]
    assert analise.definicao.campos[0].tipo is TipoCampo.NUMERO
    assert analise.definicao.campos[0].obrigatorio is True
    assert analise.tipos_calculados == {
        "ruptura_28d": TipoFormula.DATA,
        "resistencia_mpa": TipoFormula.NUMERO,
        "conforme": TipoFormula.BOOLEANO,
    }


def test_definicao_sem_campos_e_valida():
    # act / assert
    assert validar_definicao({"campos": []}) == ()


def test_exigir_definicao_valida_devolve_a_definicao():
    # act
    definicao = exigir_definicao_valida(CORPO_DE_PROVA)

    # assert
    assert len(definicao.campos) == 7


def test_exigir_definicao_valida_levanta_com_todos_os_erros():
    # arrange
    invalida = _definicao({"id": "a", "tipo": "xyz", "rotulo": "A"}, {"tipo": "texto"})

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        exigir_definicao_valida(invalida)

    # assert
    assert len(excecao.value.erros) >= 2


def test_selecao_com_opcoes_vira_tupla_no_campo():
    # arrange
    definicao = _definicao(
        {"id": "r", "tipo": "selecao", "rotulo": "R", "opcoes": ["Aprovado", "Reprovado"]}
    )

    # act
    campo = analisar_definicao(definicao).definicao.campos[0]

    # assert
    assert campo.opcoes == ("Aprovado", "Reprovado")


# --- estrutura global ---


@pytest.mark.parametrize("definicao", [None, [], "texto", 5, {}, {"campos": "x"}, {"campos": None}])
def test_definicao_sem_a_lista_campos_tem_erro_global_em_campos(definicao: object):
    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == ["campos"]


@pytest.mark.parametrize("campo_invalido", [None, "texto", 5, [], ["id"]])
def test_campo_que_nao_e_objeto_e_localizado_pelo_indice(campo_invalido: object):
    # act
    erros = _erros({"campos": [campo_invalido]})

    # assert
    assert erros == [("campos[0]", "Cada campo deve ser um objeto.")]


# --- id ---


@pytest.mark.parametrize(
    "campo", [{"tipo": "texto", "rotulo": "A"}, {"id": None, "tipo": "texto", "rotulo": "A"}]
)
def test_id_ausente_usa_o_indice(campo: dict[str, object]):
    # act / assert
    assert _campos_com_erro(_definicao({"id": "ok", "tipo": "texto", "rotulo": "O"}, campo)) == [
        "campos[1].id"
    ]


@pytest.mark.parametrize(
    "id_invalido", ["", " ", 5, True, ["a"], "1abc", "com espaço", "a-b", "ação", "a.b"]
)
def test_id_com_formato_invalido_usa_o_indice(id_invalido: object):
    # act
    erros = _erros(_definicao({"id": id_invalido, "tipo": "texto", "rotulo": "A"}))

    # assert
    assert [campo for campo, _ in erros] == ["campos[0].id"]


def test_id_duplicado_aponta_a_segunda_ocorrencia_pelo_indice():
    # arrange
    definicao = _definicao(
        {"id": "a", "tipo": "texto", "rotulo": "A"},
        {"id": "b", "tipo": "texto", "rotulo": "B"},
        {"id": "a", "tipo": "texto", "rotulo": "A de novo"},
    )

    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == ["campos[2].id"]
    assert "duplicado" in erros[0][1]


@pytest.mark.parametrize("reservado", ["pi", "se", "min", "max", "media", "soma", "dias"])
def test_id_reservado_e_rejeitado(reservado: str):
    # act
    erros = _erros(_definicao({"id": reservado, "tipo": "texto", "rotulo": "A"}))

    # assert
    assert [campo for campo, _ in erros] == ["campos[0].id"]
    assert "reservado" in erros[0][1]


@pytest.mark.parametrize("id_com_sublinhado_duplo", ["ensaio__umidade", "a__b__c", "__x"])
def test_id_com_sublinhado_duplo_e_reservado_aos_compartilhados(id_com_sublinhado_duplo: str):
    # act
    erros = _erros(_definicao({"id": id_com_sublinhado_duplo, "tipo": "texto", "rotulo": "A"}))

    # assert
    assert [campo for campo, _ in erros] == ["campos[0].id"]
    assert "__" in erros[0][1]


# --- tipo, rótulo e propriedades ---


def test_tipo_desconhecido_e_localizado_pelo_id():
    # act
    erros = _erros(_definicao({"id": "a", "tipo": "telefone", "rotulo": "A"}))

    # assert
    assert [campo for campo, _ in erros] == ["a.tipo"]
    assert "telefone" in erros[0][1]


@pytest.mark.parametrize("tipo", [None, 5, ["texto"]])
def test_tipo_ausente_ou_que_nao_e_texto_e_rejeitado(tipo: object):
    # act
    campos = _campos_com_erro(_definicao({"id": "a", "tipo": tipo, "rotulo": "A"}))

    # assert
    assert campos == ["a.tipo"]


def test_tipo_ausente_tambem_e_erro():
    # act
    assert _campos_com_erro(_definicao({"id": "a", "rotulo": "A"})) == ["a.tipo"]


@pytest.mark.parametrize("rotulo", [None, "", "  ", 5])
def test_rotulo_obrigatorio_e_nao_vazio(rotulo: object):
    # act
    campos = _campos_com_erro(_definicao({"id": "a", "tipo": "texto", "rotulo": rotulo}))

    # assert
    assert campos == ["a.rotulo"]


def test_propriedade_que_o_tipo_nao_aceita_e_rejeitada():
    # act
    erros = _erros(_definicao({"id": "a", "tipo": "texto", "rotulo": "A", "unidade": "kg"}))

    # assert
    assert [campo for campo, _ in erros] == ["a.unidade"]
    assert "texto" in erros[0][1]


def test_propriedade_com_erro_de_digitacao_nao_e_ignorada_em_silencio():
    # act
    campos = _campos_com_erro(
        _definicao({"id": "a", "tipo": "texto", "rotulo": "A", "obrigatório": True})
    )

    # assert
    assert campos == ["a.obrigatório"]


@pytest.mark.parametrize("valor", ["sim", 1, None, []])
def test_obrigatorio_deve_ser_booleano(valor: object):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "a", "tipo": "texto", "rotulo": "A", "obrigatorio": valor})
    )

    # assert
    assert campos == ["a.obrigatorio"]


def test_unidade_deve_ser_texto():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "numero", "rotulo": "A", "unidade": 5})
    ) == ["a.unidade"]


# --- casas_decimais ---


@pytest.mark.parametrize("casas", [0, 1, 6])
def test_casas_decimais_validas_em_numero(casas: int):
    # act / assert
    assert not _erros(
        _definicao({"id": "a", "tipo": "numero", "rotulo": "A", "casas_decimais": casas})
    )


@pytest.mark.parametrize("casas", [-1, 1.5, "2", True, None, [2]])
def test_casas_decimais_deve_ser_inteiro_nao_negativo(casas: object):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "a", "tipo": "numero", "rotulo": "A", "casas_decimais": casas})
    )

    # assert
    assert campos == ["a.casas_decimais"]


@pytest.mark.parametrize("tipo", ["texto", "data", "sim_nao", "secao", "foto", "localizacao"])
def test_casas_decimais_em_tipo_nao_numerico_e_rejeitada(tipo: str):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "a", "tipo": tipo, "rotulo": "A", "casas_decimais": 2})
    )

    # assert
    assert campos == ["a.casas_decimais"]


def test_casas_decimais_em_calculado_numerico_e_aceita():
    # act / assert: é o caso de resistencia_mpa do corpo de prova
    assert validar_definicao(CORPO_DE_PROVA) == ()


@pytest.mark.parametrize("formula", ["n > 1", "d + dias(1)"])
def test_casas_decimais_em_calculado_booleano_ou_data_e_rejeitada(formula: str):
    # arrange
    definicao = _definicao(
        {"id": "n", "tipo": "numero", "rotulo": "N"},
        {"id": "d", "tipo": "data", "rotulo": "D"},
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": formula, "casas_decimais": 2},
    )

    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == ["c.casas_decimais"]
    assert "numérico" in erros[0][1]


# --- selecao ---


@pytest.mark.parametrize(
    "opcoes",
    [None, [], "A,B", ["A", 1], ["A", ""], ["A", "A"], [["A"]], {"A": 1}],
)
def test_opcoes_de_selecao_devem_ser_lista_nao_vazia_de_textos_sem_repeticao(opcoes: object):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "s", "tipo": "selecao", "rotulo": "S", "opcoes": opcoes})
    )

    # assert
    assert campos == ["s.opcoes"]


def test_selecao_sem_opcoes_e_rejeitada():
    # act
    assert _campos_com_erro(_definicao({"id": "s", "tipo": "selecao", "rotulo": "S"})) == [
        "s.opcoes"
    ]


def test_opcoes_em_outro_tipo_e_rejeitada():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "texto", "rotulo": "A", "opcoes": ["x"]})
    ) == ["a.opcoes"]


# --- foto ---


@pytest.mark.parametrize("maximo", [1, 5])
def test_maximo_de_foto_valido(maximo: int):
    # act / assert
    assert not _erros(_definicao({"id": "f", "tipo": "foto", "rotulo": "F", "maximo": maximo}))


@pytest.mark.parametrize("maximo", [0, -1, 1.5, "3", True, None])
def test_maximo_de_foto_deve_ser_inteiro_a_partir_de_1(maximo: object):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "f", "tipo": "foto", "rotulo": "F", "maximo": maximo})
    )

    # assert
    assert campos == ["f.maximo"]


def test_maximo_em_outro_tipo_e_rejeitado():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "numero", "rotulo": "A", "maximo": 2})
    ) == ["a.maximo"]


# --- compartilhado ---


@pytest.mark.parametrize("tipo", ["texto", "numero", "data", "sim_nao", "localizacao", "foto"])
def test_compartilhado_e_aceito_nos_tipos_comuns(tipo: str):
    # arrange
    campo = {"id": "a", "tipo": tipo, "rotulo": "A", "compartilhado": True}
    if tipo == "selecao":
        campo["opcoes"] = ["x"]

    # act / assert
    assert not _erros(_definicao(campo))


def test_compartilhado_em_selecao_e_calculado_e_aceito():
    # arrange
    definicao = _definicao(
        {"id": "s", "tipo": "selecao", "rotulo": "S", "opcoes": ["x"], "compartilhado": True},
        {"id": "n", "tipo": "numero", "rotulo": "N"},
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "n * 2", "compartilhado": True},
    )

    # act / assert
    assert not _erros(definicao)


def test_compartilhado_em_secao_e_rejeitado_com_mensagem_propria():
    # act
    erros = _erros(_definicao({"id": "s", "tipo": "secao", "rotulo": "S", "compartilhado": True}))

    # assert
    assert [campo for campo, _ in erros] == ["s.compartilhado"]
    assert "seção" in erros[0][1] or "secao" in erros[0][1]


def test_compartilhado_em_referencia_e_rejeitado():
    # act
    campos = _campos_com_erro(
        _definicao(
            {
                "id": "r",
                "tipo": "referencia",
                "rotulo": "R",
                "formulario": "ensaio",
                "compartilhado": True,
            }
        ),
        ORIGENS,
    )

    # assert
    assert campos == ["r.compartilhado"]


def test_compartilhado_deve_ser_booleano():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "texto", "rotulo": "A", "compartilhado": "sim"})
    ) == ["a.compartilhado"]


# --- referencia ---


def test_referencia_para_formulario_existente_e_valida():
    # act / assert
    assert not _erros(
        _definicao(
            {"id": "ensaio", "tipo": "referencia", "rotulo": "Ensaio", "formulario": "ensaio"}
        ),
        ORIGENS,
    )


@pytest.mark.parametrize("formulario", [None, "", 5])
def test_referencia_sem_formulario_e_rejeitada(formulario: object):
    # act
    campos = _campos_com_erro(
        _definicao({"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": formulario}),
        ORIGENS,
    )

    # assert
    assert campos == ["r.formulario"]


def test_referencia_sem_a_chave_formulario_e_rejeitada():
    # act
    assert _campos_com_erro(
        _definicao({"id": "r", "tipo": "referencia", "rotulo": "R"}), ORIGENS
    ) == ["r.formulario"]


def test_referencia_para_formulario_inexistente_e_rejeitada():
    # act
    erros = _erros(
        _definicao({"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": "fantasma"}),
        ORIGENS,
    )

    # assert
    assert [campo for campo, _ in erros] == ["r.formulario"]
    assert "fantasma" in erros[0][1] and "não existe" in erros[0][1]


def test_sem_origens_informadas_toda_referencia_aponta_formulario_inexistente():
    # act
    assert _campos_com_erro(
        _definicao({"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": "ensaio"})
    ) == ["r.formulario"]


def test_formulario_em_campo_que_nao_e_referencia_e_rejeitado():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "texto", "rotulo": "A", "formulario": "x"})
    ) == ["a.formulario"]


# --- fórmulas ---


def _com_referencia(*campos: dict[str, object]) -> dict[str, object]:
    return _definicao(
        {"id": "ensaio", "tipo": "referencia", "rotulo": "Ensaio", "formulario": "ensaio"},
        {"id": "n", "tipo": "numero", "rotulo": "N"},
        *campos,
    )


def test_formula_usa_campo_compartilhado_pelo_nome_composto():
    # arrange
    definicao = _com_referencia(
        {"id": "seco", "tipo": "calculado", "rotulo": "S", "formula": "n * (1 - ensaio__umidade)"},
        {"id": "prazo", "tipo": "calculado", "rotulo": "P", "formula": "ensaio__data + dias(2)"},
    )

    # act
    analise = analisar_definicao(definicao, ORIGENS)

    # assert
    assert analise.erros == ()
    assert analise.tipos_calculados == {"seco": TipoFormula.NUMERO, "prazo": TipoFormula.DATA}


def test_formula_com_campo_que_a_origem_nao_compartilha_e_rejeitada():
    # arrange
    definicao = _com_referencia(
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "ensaio__densidade * 2"}
    )

    # act
    erros = _erros(definicao, ORIGENS)

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]
    assert "ensaio" in erros[0][1] and "densidade" in erros[0][1] and "compartilha" in erros[0][1]


def test_formula_com_compartilhado_de_tipo_que_nao_entra_em_formula_e_rejeitada():
    # arrange: "operador" é texto na origem
    definicao = _com_referencia(
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "ensaio__operador"}
    )

    # act
    erros = _erros(definicao, ORIGENS)

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]
    assert "texto" in erros[0][1]


def test_erro_de_formula_traz_posicao_e_localizacao_pelo_id():
    # arrange
    definicao = _definicao(
        {"id": "n", "tipo": "numero", "rotulo": "N"},
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "n + __import__('os')"},
    )

    # act
    erros = validar_definicao(definicao)

    # assert
    assert [e.campo for e in erros] == ["c.formula"]
    assert erros[0].posicao == Posicao(4, 20)


@pytest.mark.parametrize("formula", [None, 5, ["n"]])
def test_calculado_exige_formula_em_texto(formula: object):
    # act
    assert _campos_com_erro(
        _definicao({"id": "c", "tipo": "calculado", "rotulo": "C", "formula": formula})
    ) == ["c.formula"]


def test_calculado_sem_a_chave_formula_e_rejeitado():
    # act
    assert _campos_com_erro(_definicao({"id": "c", "tipo": "calculado", "rotulo": "C"})) == [
        "c.formula"
    ]


def test_formula_em_campo_que_nao_e_calculado_e_rejeitada():
    # act
    assert _campos_com_erro(
        _definicao({"id": "a", "tipo": "numero", "rotulo": "A", "formula": "1 + 1"})
    ) == ["a.formula"]


def test_formula_com_campo_inexistente_e_rejeitada_ao_publicar():
    # act
    erros = _erros(_definicao({"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "x + 1"}))

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]
    assert "'x'" in erros[0][1]


@pytest.mark.parametrize("tipo", ["texto", "selecao", "secao", "localizacao", "foto"])
def test_formula_nao_pode_referenciar_campo_de_tipo_proibido(tipo: str):
    # arrange
    campo = {"id": "t", "tipo": tipo, "rotulo": "T"}
    if tipo == "selecao":
        campo["opcoes"] = ["x"]
    definicao = _definicao(campo, {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "t"})

    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]
    assert tipo in erros[0][1]


def test_formula_nao_pode_referenciar_campo_referencia():
    # act
    erros = _erros(
        _com_referencia({"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "ensaio"}),
        ORIGENS,
    )

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]


def test_tipos_incompativeis_na_formula_sao_rejeitados():
    # arrange
    definicao = _definicao(
        {"id": "d", "tipo": "data", "rotulo": "D"},
        {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "d * 2"},
    )

    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == ["c.formula"]
    assert "data" in erros[0][1]


def test_duracao_como_resultado_final_e_rejeitada():
    # act
    assert _campos_com_erro(
        _definicao({"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "dias(3)"})
    ) == ["c.formula"]


def test_calculado_que_depende_de_calculado_usa_o_tipo_inferido_do_primeiro():
    # arrange: "final" vem antes de "prazo" na lista, mas depende dele
    definicao = _definicao(
        {"id": "d", "tipo": "data", "rotulo": "D"},
        {"id": "final", "tipo": "calculado", "rotulo": "F", "formula": "prazo > d"},
        {"id": "prazo", "tipo": "calculado", "rotulo": "P", "formula": "d + dias(1)"},
    )

    # act
    analise = analisar_definicao(definicao)

    # assert
    assert analise.erros == ()
    assert analise.tipos_calculados["final"] is TipoFormula.BOOLEANO


@pytest.mark.parametrize(
    ("formulas", "campos_do_ciclo"),
    [
        ({"a": "b + 1", "b": "a + 1"}, ("a", "b")),
        ({"a": "b + 1", "b": "c + 1", "c": "a + 1"}, ("a", "b", "c")),
        ({"a": "a + 1"}, ("a",)),
    ],
)
def test_ciclo_entre_campos_e_rejeitado_citando_os_campos(
    formulas: dict[str, str], campos_do_ciclo: tuple[str, ...]
):
    # arrange
    definicao = _definicao(
        *(
            {"id": id_, "tipo": "calculado", "rotulo": id_, "formula": f}
            for id_, f in formulas.items()
        )
    )

    # act
    erros = _erros(definicao)

    # assert
    assert [campo for campo, _ in erros] == [f"{campos_do_ciclo[0]}.formula"]
    for campo in campos_do_ciclo:
        assert campo in erros[0][1]


def test_calculado_que_usa_calculado_com_formula_invalida_nao_gera_erro_em_cascata():
    # arrange
    definicao = _definicao(
        {"id": "a", "tipo": "calculado", "rotulo": "A", "formula": "1 +"},
        {"id": "b", "tipo": "calculado", "rotulo": "B", "formula": "a * 2"},
    )

    # act
    campos = _campos_com_erro(definicao)

    # assert: só a origem do problema é apontada
    assert campos == ["a.formula"]


# --- vários erros de uma vez ---


def test_devolve_todos_os_erros_de_uma_vez_e_nao_so_o_primeiro():
    # arrange
    definicao = _definicao(
        {"id": "pi", "tipo": "texto", "rotulo": "A"},
        {"id": "b", "tipo": "telefone", "rotulo": "B"},
        {"id": "c", "tipo": "selecao", "rotulo": "C", "opcoes": []},
        {"id": "d", "tipo": "numero", "rotulo": "D", "casas_decimais": -1},
        {"id": "e", "tipo": "calculado", "rotulo": "E", "formula": "x + 1"},
        {"id": "f", "tipo": "foto", "rotulo": "F", "maximo": 0},
    )

    # act
    campos = set(_campos_com_erro(definicao))

    # assert
    assert campos == {
        "campos[0].id",
        "b.tipo",
        "c.opcoes",
        "d.casas_decimais",
        "e.formula",
        "f.maximo",
    }


def test_varios_erros_no_mesmo_campo_sao_todos_reportados():
    # act
    campos = _campos_com_erro(
        _definicao(
            {"id": "a", "tipo": "numero", "rotulo": "", "casas_decimais": -1, "obrigatorio": "x"}
        )
    )

    # assert
    assert sorted(campos) == ["a.casas_decimais", "a.obrigatorio", "a.rotulo"]


def test_campo_com_erro_nao_impede_validar_os_outros():
    # arrange
    definicao = _definicao(
        {"id": "a", "tipo": "telefone", "rotulo": "A"},
        {"id": "n", "tipo": "numero", "rotulo": "N", "casas_decimais": "x"},
    )

    # act
    campos = _campos_com_erro(definicao)

    # assert
    assert sorted(campos) == ["a.tipo", "n.casas_decimais"]


def test_definicao_invalida_nao_expoe_definicao_parcial():
    # act
    analise = analisar_definicao(_definicao({"id": "a", "tipo": "telefone", "rotulo": "A"}))

    # assert
    assert analise.definicao is None and analise.erros


def test_validar_nao_modifica_a_entrada():
    # arrange
    import copy

    original = copy.deepcopy(CORPO_DE_PROVA)

    # act
    validar_definicao(CORPO_DE_PROVA)

    # assert
    assert CORPO_DE_PROVA == original
