import ast
import dataclasses
from pathlib import Path

import pytest

from forms import models
from forms.models import (
    Campo,
    CicloDeDependencia,
    Definicao,
    DefinicaoInvalida,
    ErroDeCampo,
    ErroDeDominio,
    ExclusaoBloqueada,
    FormulaInvalida,
    Formulario,
    NaoEncontrado,
    Posicao,
    Registro,
    RegistroInvalido,
    ResultadoCalculado,
    TipoCampo,
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
    assert campo.maximo is None


def test_tipo_campo_tem_os_dez_tipos_do_contrato():
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
        "foto",
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
        NaoEncontrado("x"),
        ExclusaoBloqueada("x"),
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
