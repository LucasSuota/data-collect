import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from forms.dominio.formulas import ValorDeCampo, calcular_campos
from forms.dominio.models import Campo, CicloDeDependencia, ResultadoCalculado, TipoCampo

D = Decimal

# Trecho do template de corpo de prova (AGENTS.md §5.2), escrito aqui para o teste não
# depender do arquivo de template, que é de outra issue.
CAMPOS_CORPO_DE_PROVA = (
    Campo(id="fck_mpa", tipo=TipoCampo.NUMERO, rotulo="fck especificado", unidade="MPa"),
    Campo(id="diametro_mm", tipo=TipoCampo.NUMERO, rotulo="Diâmetro", unidade="mm"),
    Campo(id="data_moldagem", tipo=TipoCampo.DATA, rotulo="Data de moldagem"),
    Campo(id="carga_kn", tipo=TipoCampo.NUMERO, rotulo="Carga de ruptura", unidade="kN"),
    Campo(
        id="ruptura_28d",
        tipo=TipoCampo.CALCULADO,
        rotulo="Ruptura aos 28 dias",
        formula="data_moldagem + dias(28)",
    ),
    Campo(
        id="resistencia_mpa",
        tipo=TipoCampo.CALCULADO,
        rotulo="Resistência",
        unidade="MPa",
        casas_decimais=1,
        formula="carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)",
    ),
    Campo(
        id="conforme",
        tipo=TipoCampo.CALCULADO,
        rotulo="Conforme?",
        formula="resistencia_mpa >= fck_mpa",
    ),
)


def _calculado(id: str, formula: str, **extras: object) -> Campo:
    return Campo(id=id, tipo=TipoCampo.CALCULADO, rotulo=id, formula=formula, **extras)


def test_corpo_de_prova_do_exemplo_calcula_resistencia_prazo_e_conformidade():
    # arrange: cilindro de 100 mm de diâmetro rompido com 200 kN
    entradas = {
        "fck_mpa": D("25"),
        "diametro_mm": D("100"),
        "data_moldagem": date(2026, 11, 1),
        "carga_kn": D("200"),
    }

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert set(resultado) == {"ruptura_28d", "resistencia_mpa", "conforme"}
    assert resultado["ruptura_28d"] == ResultadoCalculado("2026-11-29", None)
    assert resultado["conforme"] == ResultadoCalculado(True, None)
    resistencia = D(resultado["resistencia_mpa"].valor)
    assert abs(resistencia - D("25.46479089")) < D("0.00000001")
    assert resultado["resistencia_mpa"].erro is None


def test_casas_decimais_nao_arredonda_o_valor_guardado():
    # arrange: com casas_decimais=1, o valor continua com a precisão total
    entradas = {"diametro_mm": D("100"), "carga_kn": D("200")}

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert len(resultado["resistencia_mpa"].valor.split(".")[1]) > 10


def test_conformidade_usa_o_valor_sem_arredondar():
    # arrange: 25,46... com fck 25,5 não é conforme, mesmo que arredondado fosse 25,5
    entradas = {
        "fck_mpa": D("25.47"),
        "diametro_mm": D("100"),
        "carga_kn": D("200"),
        "data_moldagem": date(2026, 11, 1),
    }

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert resultado["conforme"].valor is False


def test_entrada_vazia_gera_valor_nulo_e_erro_nulo():
    # arrange: falta a carga de ruptura
    entradas = {"fck_mpa": D("25"), "diametro_mm": D("100"), "data_moldagem": date(2026, 11, 1)}

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert resultado["resistencia_mpa"] == ResultadoCalculado(None, None)
    assert resultado["conforme"] == ResultadoCalculado(None, None)
    assert resultado["ruptura_28d"] == ResultadoCalculado("2026-11-29", None)


def test_sem_nenhuma_entrada_todos_os_calculados_ficam_vazios():
    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, {})

    # assert
    assert all(r == ResultadoCalculado(None, None) for r in resultado.values())


def test_divisao_por_zero_vira_erro_no_campo_e_nao_derruba_os_outros():
    # arrange: diâmetro zero quebra a resistência, mas a data de ruptura continua certa
    entradas = {
        "fck_mpa": D("25"),
        "diametro_mm": D("0"),
        "carga_kn": D("200"),
        "data_moldagem": date(2026, 11, 1),
    }

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert resultado["resistencia_mpa"].valor is None
    assert "zero" in resultado["resistencia_mpa"].erro.lower()
    assert resultado["ruptura_28d"] == ResultadoCalculado("2026-11-29", None)


def test_dependencia_com_erro_propaga_o_erro_citando_o_campo_de_origem():
    # arrange
    entradas = {"fck_mpa": D("25"), "diametro_mm": D("0"), "carga_kn": D("200")}

    # act
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    erro = resultado["conforme"].erro
    assert resultado["conforme"].valor is None
    assert "resistencia_mpa" in erro and "zero" in erro.lower()


def test_cadeia_de_tres_campos_propaga_o_erro_ate_o_fim_citando_cada_origem():
    # arrange
    campos = (
        Campo(id="x", tipo=TipoCampo.NUMERO, rotulo="x"),
        _calculado("a", "1 / x"),
        _calculado("b", "a + 1"),
        _calculado("c", "b * 2"),
    )

    # act
    resultado = calcular_campos(campos, {"x": D("0")})

    # assert
    assert "zero" in resultado["a"].erro.lower()
    assert "'a'" in resultado["b"].erro
    assert "'b'" in resultado["c"].erro and "'a'" in resultado["c"].erro


def test_a_ordem_da_definicao_nao_importa_so_as_dependencias():
    # arrange: "conforme" vem antes de "resistencia" na lista
    campos = (
        Campo(id="x", tipo=TipoCampo.NUMERO, rotulo="x"),
        _calculado("c", "b * 2"),
        _calculado("b", "a + 1"),
        _calculado("a", "x * 10"),
    )

    # act
    resultado = calcular_campos(campos, {"x": D("1")})

    # assert
    assert resultado["c"] == ResultadoCalculado("22", None)
    assert list(resultado) == ["c", "b", "a"]  # a saída segue a ordem da definição


def test_calculado_booleano_e_de_data_saem_no_formato_json():
    # arrange
    campos = (
        Campo(id="d", tipo=TipoCampo.DATA, rotulo="d"),
        Campo(id="n", tipo=TipoCampo.NUMERO, rotulo="n"),
        _calculado("prazo", "d + dias(n)"),
        _calculado("ok", "n > 3"),
        _calculado("dobro", "n * 2"),
    )

    # act
    resultado = calcular_campos(campos, {"d": date(2026, 1, 30), "n": D("5")})

    # assert
    assert resultado["prazo"].valor == "2026-02-04"
    assert resultado["ok"].valor is True
    assert resultado["dobro"].valor == "10"


def test_numero_calculado_nunca_sai_em_notacao_cientifica():
    # arrange
    campos = (Campo(id="n", tipo=TipoCampo.NUMERO, rotulo="n"), _calculado("m", "n * 1000"))

    # act
    resultado = calcular_campos(campos, {"n": D("1E+3")})

    # assert
    assert resultado["m"].valor == "1000000"


# --- campos compartilhados ---


def test_campo_compartilhado_entra_na_formula_pelo_nome_composto():
    # arrange
    campos = (_calculado("seco", "ensaio__umidade * 2"),)
    compartilhados = {"ensaio__umidade": ValorDeCampo(D("12.5"))}

    # act
    resultado = calcular_campos(campos, {}, compartilhados)

    # assert
    assert resultado["seco"] == ResultadoCalculado("25.0", None)


def test_compartilhado_vazio_deixa_o_resultado_vazio():
    # arrange: referência sem valor, ou campo que a versão antiga da origem não tem
    campos = (_calculado("seco", "ensaio__umidade * 2"),)

    # act
    com_vazio = calcular_campos(campos, {}, {"ensaio__umidade": ValorDeCampo(None)})
    ausente = calcular_campos(campos, {})

    # assert
    assert com_vazio["seco"] == ResultadoCalculado(None, None)
    assert ausente["seco"] == ResultadoCalculado(None, None)


def test_compartilhado_com_erro_na_origem_propaga_citando_o_campo_de_origem():
    # arrange
    campos = (_calculado("seco", "ensaio__umidade * 2"),)
    compartilhados = {"ensaio__umidade": ValorDeCampo(None, "Divisão por zero.")}

    # act
    resultado = calcular_campos(campos, {}, compartilhados)

    # assert
    assert resultado["seco"].valor is None
    assert "ensaio__umidade" in resultado["seco"].erro
    assert "Divisão por zero" in resultado["seco"].erro


def test_compartilhado_de_data_funciona_em_aritmetica_de_datas():
    # arrange
    campos = (_calculado("prazo", "ensaio__data + dias(2)"),)
    compartilhados = {"ensaio__data": ValorDeCampo(date(2026, 1, 1))}

    # act / assert
    assert calcular_campos(campos, {}, compartilhados)["prazo"].valor == "2026-01-03"


# --- uma única função de cálculo e erros de definição ---


def test_calcular_e_deterministico_e_nao_altera_as_entradas():
    # arrange
    entradas = {"diametro_mm": D("100"), "carga_kn": D("200")}
    copia = dict(entradas)

    # act
    primeiro = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)
    segundo = calcular_campos(CAMPOS_CORPO_DE_PROVA, entradas)

    # assert
    assert primeiro == segundo
    assert entradas == copia


def test_ciclo_na_definicao_e_barrado_tambem_no_calculo():
    # arrange: uma definição publicada nunca teria isso, mas o cálculo não pode girar em falso
    campos = (_calculado("a", "b + 1"), _calculado("b", "a + 1"))

    # act / assert
    with pytest.raises(CicloDeDependencia):
        calcular_campos(campos, {})


def test_definicao_sem_campos_calculados_devolve_dicionario_vazio():
    # act / assert
    assert calcular_campos((Campo(id="x", tipo=TipoCampo.NUMERO, rotulo="x"),), {}) == {}


def test_resultado_serializa_como_json_valor_e_erro():
    # arrange
    resultado = calcular_campos(CAMPOS_CORPO_DE_PROVA, {"data_moldagem": date(2026, 11, 1)})

    # act
    texto = json.dumps({k: [v.valor, v.erro] for k, v in resultado.items()})

    # assert
    assert json.loads(texto)["ruptura_28d"] == ["2026-11-29", None]


def test_modulo_de_formulas_nao_e_importado_por_camadas_acima():
    # assert: o núcleo de cálculo não depende de api, servico, repositorio nem de IA
    import ast

    from forms.dominio import formulas

    arvore = ast.parse(Path(formulas.__file__).read_text(encoding="utf-8"))
    importados = {
        (no.module or "").split(".")[-1] if (no.module or "").startswith("forms.") else ""
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
    }
    assert importados <= {"models", "tipos_campo", ""}
