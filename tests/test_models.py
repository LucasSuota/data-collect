import ast
import dataclasses
from pathlib import Path

import pytest

from forms.dominio import models
from forms.dominio.models import (
    Campo,
    CicloDeDependencia,
    Definicao,
    DefinicaoInvalida,
    ErroDeCalculo,
    ErroDeCampo,
    ErroDeDominio,
    ErrosDoFormulario,
    ExclusaoBloqueada,
    FormulaInvalida,
    Formulario,
    LoteInvalido,
    NaoEncontrado,
    Posicao,
    Registro,
    RegistroInvalido,
    ResultadoCalculado,
    TipoCampo,
    ValorInvalido,
    Versao,
)


def _campo() -> Campo:
    return Campo(id="fck_mpa", tipo=TipoCampo.NUMERO, rotulo="fck especificado")


def _instancias_imutaveis() -> list[tuple[object, str]]:
    campo = _campo()
    definicao = Definicao(campos=(campo,))
    return [
        (campo, "rotulo"),
        (definicao, "campos"),
        (Formulario(id=1, nome="ensaio", criado_em="2026-11-02T10:00:00"), "nome"),
        (
            Versao(
                id=1,
                formulario_id=1,
                numero=1,
                definicao=definicao,
                publicada_em="2026-11-02T10:00:00",
            ),
            "numero",
        ),
        (
            Registro(
                id=1,
                formulario_id=1,
                versao_id=1,
                dados={},
                criado_em="2026-11-02T10:00:00",
                atualizado_em="2026-11-02T10:00:00",
            ),
            "versao_id",
        ),
        (Posicao(inicio=0, fim=3), "fim"),
        (ErroDeCampo(campo="a", mensagem="erro"), "mensagem"),
        (ResultadoCalculado(valor="1", erro=None), "valor"),
    ]


@pytest.mark.parametrize(("instancia", "atributo"), _instancias_imutaveis())
def test_instancias_do_dominio_sao_imutaveis(instancia: object, atributo: str):
    # act / assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instancia, atributo, None)


def test_campo_tem_defaults_seguros():
    # act
    campo = Campo(id="x", tipo=TipoCampo.TEXTO, rotulo="X")

    # assert
    assert campo.obrigatorio is False
    assert campo.compartilhado is False
    assert campo.opcoes == ()
    assert campo.unidade is None
    assert campo.formula is None
    assert campo.casas_decimais is None
    assert campo.formulario is None


def test_tipo_campo_tem_os_nove_tipos_do_contrato():
    # assert
    assert {tipo.value for tipo in TipoCampo} == {
        "texto",
        "numero",
        "data",
        "selecao",
        "sim_nao",
        "calculado",
        "secao",
        "referencia",
        "localizacao",
    }


def test_tipo_campo_converte_a_partir_do_texto_do_json():
    # act / assert
    assert TipoCampo("sim_nao") is TipoCampo.SIM_NAO


def test_erro_de_campo_sem_posicao_por_padrao():
    # act
    erro = ErroDeCampo(campo="resistencia_mpa.formula", mensagem="Divisão por zero")

    # assert
    assert erro.posicao is None


def test_resultado_calculado_vazio_tem_valor_e_erro_nulos():
    # act
    resultado = ResultadoCalculado(valor=None, erro=None)

    # assert
    assert resultado.valor is None
    assert resultado.erro is None


def test_definicao_invalida_carrega_lista_de_erros():
    # arrange
    erros = (ErroDeCampo(campo="campos[0].id", mensagem="id ausente"),)

    # act
    excecao = DefinicaoInvalida(erros)

    # assert
    assert excecao.erros == erros


def test_registro_invalido_carrega_lista_de_erros():
    # arrange
    erros = (
        ErroDeCampo(campo="fck_mpa", mensagem="Campo obrigatório"),
        ErroDeCampo(campo="data_moldagem", mensagem="Data inválida"),
    )

    # act
    excecao = RegistroInvalido(erros)

    # assert
    assert excecao.erros == erros


def test_ciclo_cita_os_campos_envolvidos_na_mensagem():
    # act
    excecao = CicloDeDependencia(("a", "b", "a"))

    # assert
    assert excecao.campos == ("a", "b", "a")
    assert "a" in str(excecao) and "b" in str(excecao)


def test_ciclo_e_uma_definicao_invalida_com_erro_localizado():
    # act
    excecao = CicloDeDependencia(("a", "b", "a"))

    # assert
    assert isinstance(excecao, DefinicaoInvalida)
    assert [erro.campo for erro in excecao.erros] == ["a.formula"]


def test_formula_invalida_carrega_mensagem_e_posicao():
    # arrange
    posicao = Posicao(inicio=12, fim=20)

    # act
    excecao = FormulaInvalida("Função não permitida", posicao)

    # assert
    assert str(excecao) == "Função não permitida"
    assert excecao.posicao == posicao


def test_formula_invalida_aceita_posicao_ausente():
    # act
    excecao = FormulaInvalida("Fórmula vazia")

    # assert
    assert excecao.posicao is None


@pytest.mark.parametrize(
    "excecao",
    [
        DefinicaoInvalida(()),
        RegistroInvalido(()),
        CicloDeDependencia(("a", "a")),
        FormulaInvalida("x"),
        ErroDeCalculo("x"),
        NaoEncontrado("x"),
        ExclusaoBloqueada("x"),
        ValorInvalido("x"),
        LoteInvalido(()),
    ],
)
def test_excecoes_de_dominio_herdam_da_base(excecao: Exception):
    # assert
    assert isinstance(excecao, ErroDeDominio)


def test_models_nao_importa_outras_camadas():
    # arrange
    arvore = ast.parse(Path(models.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    # assert
    proibidos = {"forms", "pydantic", "fastapi", "sqlite3"}
    assert importados.isdisjoint(proibidos)


# --- conversão de e para o JSON de definição ---

DEFINICAO_COMPLETA = {
    "campos": [
        {"id": "secao_1", "tipo": "secao", "rotulo": "Dados"},
        {
            "id": "fck",
            "tipo": "numero",
            "rotulo": "fck",
            "unidade": "MPa",
            "casas_decimais": 1,
            "obrigatorio": True,
            "compartilhado": True,
        },
        {"id": "dia", "tipo": "data", "rotulo": "Dia"},
        {"id": "r", "tipo": "selecao", "rotulo": "R", "opcoes": ["A", "B"]},
        {"id": "ref", "tipo": "referencia", "rotulo": "Ref", "formulario": "ensaio"},
        {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "fck * 2"},
    ]
}


def test_definicao_faz_ida_e_volta_pelo_json_sem_perder_nada():
    # act
    definicao = Definicao.de_json(DEFINICAO_COMPLETA)

    # assert
    assert definicao.para_json() == DEFINICAO_COMPLETA


def test_de_json_monta_campos_tipados_e_imutaveis():
    # act
    definicao = Definicao.de_json(DEFINICAO_COMPLETA)
    fck, seletor = definicao.campos[1], definicao.campos[3]

    # assert
    assert fck.tipo is TipoCampo.NUMERO and fck.obrigatorio and fck.compartilhado
    assert fck.casas_decimais == 1 and fck.unidade == "MPa"
    assert seletor.opcoes == ("A", "B")
    assert isinstance(definicao.campos, tuple)


def test_para_json_omite_o_que_e_padrao():
    # act
    json_do_campo = Campo(id="a", tipo=TipoCampo.TEXTO, rotulo="A").para_json()

    # assert
    assert json_do_campo == {"id": "a", "tipo": "texto", "rotulo": "A"}


def test_para_json_nao_compartilha_estado_com_o_campo():
    # arrange
    campo = Campo(id="s", tipo=TipoCampo.SELECAO, rotulo="S", opcoes=("A",))

    # act
    campo.para_json()["opcoes"].append("B")

    # assert
    assert campo.opcoes == ("A",)


def test_lote_invalido_carrega_os_erros_agrupados_por_formulario():
    # arrange
    erro = ErroDeCampo(campo="a.tipo", mensagem="Tipo desconhecido")
    formularios = (ErrosDoFormulario(nome="proctor", erros=(erro,)),)

    # act
    excecao = LoteInvalido(formularios)

    # assert
    assert excecao.formularios == formularios
    assert "proctor" in str(excecao) and "a.tipo" in str(excecao)
