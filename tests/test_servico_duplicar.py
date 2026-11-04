"""Duplicar formulário (AGENTS.md §2.10)."""

from datetime import UTC, datetime

import pytest

from forms import servico
from forms.models import DefinicaoInvalida, ExclusaoBloqueada, NaoEncontrado
from forms.repositorio import listar_dependencias

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEPOIS = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)

ENSAIO = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "compartilhado": True},
        {"id": "obs", "tipo": "texto", "rotulo": "Observação"},
    ]
}
PROCTOR = {
    "campos": [
        {
            "id": "ensaio",
            "tipo": "referencia",
            "rotulo": "Ensaio",
            "formulario": "ensaio",
            "obrigatorio": True,
        },
        {"id": "massa", "tipo": "numero", "rotulo": "Massa"},
        {
            "id": "seca",
            "tipo": "calculado",
            "rotulo": "Massa seca",
            "formula": "massa * (1 - ensaio__umidade)",
        },
    ]
}


def _criar(conexao, nome, definicao=ENSAIO):
    return servico.criar_formulario(conexao, nome, definicao, AGORA)


def _definicao_da_versao_atual(conexao, formulario_id: int) -> dict:
    return servico.obter_formulario(conexao, formulario_id).versao_atual.definicao.para_json()


# --- a cópia ---


def test_a_copia_tem_a_definicao_do_original_e_nasce_na_versao_1(conexao):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, DEPOIS)

    # assert
    assert copia.formulario.id != original.formulario.id
    assert copia.versao.numero == 1
    assert copia.versao.definicao == original.versao.definicao
    assert copia.formulario.criado_em == "2026-11-03T10:00:00+00:00"


def test_a_copia_usa_a_versao_atual_do_original_e_nao_herda_o_historico(conexao):
    # arrange: o original está na versão 2
    original = _criar(conexao, "ensaio")
    nova = {"campos": [*ENSAIO["campos"], {"id": "data", "tipo": "data", "rotulo": "Data"}]}
    servico.publicar_versao(conexao, original.formulario.id, nova, DEPOIS)

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, DEPOIS)

    # assert
    assert [c.id for c in copia.versao.definicao.campos] == ["umidade", "obs", "data"]
    assert [v.numero for v in servico.listar_versoes(conexao, copia.formulario.id)] == [1]


def test_a_copia_nao_leva_registros(conexao):
    # arrange
    original = _criar(conexao, "ensaio")
    servico.criar_registro(
        conexao, original.formulario.id, original.versao.id, {"umidade": "10"}, AGORA
    )

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA)

    # assert
    assert servico.listar_registros(conexao, copia.formulario.id).total == 0
    assert servico.listar_registros(conexao, original.formulario.id).total == 1


def test_a_copia_fica_na_mesma_pasta_do_original(conexao):
    # arrange
    pasta = servico.criar_pasta(conexao, "Obras", None, AGORA)
    original = servico.criar_formulario(conexao, "ensaio", ENSAIO, AGORA, pasta.id)

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA)

    # assert
    assert copia.formulario.pasta_id == pasta.id
    assert servico.obter_formulario(conexao, copia.formulario.id).formulario.pasta_id == pasta.id


def test_o_original_nao_muda_em_nada(conexao):
    # arrange
    original = _criar(conexao, "ensaio")
    antes = servico.obter_formulario(conexao, original.formulario.id)

    # act
    servico.duplicar_formulario(conexao, original.formulario.id, "outro", DEPOIS)

    # assert
    assert servico.obter_formulario(conexao, original.formulario.id) == antes


# --- nome ---


def test_sem_nome_o_padrao_e_o_nome_com_copia(conexao):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA)

    # assert
    assert copia.formulario.nome == "ensaio (cópia)"


def test_nomes_padrao_sucessivos_ganham_numero(conexao):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    nomes = [
        servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA).formulario.nome
        for _ in range(3)
    ]

    # assert
    assert nomes == ["ensaio (cópia)", "ensaio (cópia 2)", "ensaio (cópia 3)"]


def test_nome_padrao_pula_um_nome_ocupado_sem_diferenciar_caixa(conexao):
    # arrange: "ENSAIO (CÓPIA)" já existe, então a unicidade (sem caixa) manda ir para o 2
    original = _criar(conexao, "ensaio")
    _criar(conexao, "ENSAIO (CÓPIA)")

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA)

    # assert
    assert copia.formulario.nome == "ensaio (cópia 2)"


def test_duplicar_a_copia_acrescenta_copia_ao_nome_da_copia(conexao):
    # arrange
    original = _criar(conexao, "ensaio")
    copia = servico.duplicar_formulario(conexao, original.formulario.id, None, AGORA)

    # act
    neta = servico.duplicar_formulario(conexao, copia.formulario.id, None, AGORA)

    # assert
    assert neta.formulario.nome == "ensaio (cópia) (cópia)"


def test_nome_informado_e_usado(conexao):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    copia = servico.duplicar_formulario(conexao, original.formulario.id, "  Ensaio B  ", AGORA)

    # assert
    assert copia.formulario.nome == "Ensaio B"


@pytest.mark.parametrize("repetido", ["ensaio", "ENSAIO", "  Ensaio  "])
def test_nome_informado_e_repetido_gera_erro_no_campo_nome_e_nao_cria_nada(conexao, repetido):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.duplicar_formulario(conexao, original.formulario.id, repetido, AGORA)

    # assert
    assert [e.campo for e in excecao.value.erros] == ["nome"]
    assert len(servico.listar_formularios(conexao)) == 1


def test_nome_informado_em_branco_e_erro_e_nao_vira_o_padrao(conexao):
    # arrange
    original = _criar(conexao, "ensaio")

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.duplicar_formulario(conexao, original.formulario.id, "   ", AGORA)

    # assert
    assert [e.campo for e in excecao.value.erros] == ["nome"]


def test_duplicar_formulario_inexistente_levanta_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.duplicar_formulario(conexao, 99, None, AGORA)


# --- relações entre formulários (§2.7) ---


def test_a_copia_de_um_dependente_depende_das_mesmas_origens(conexao):
    # arrange
    ensaio = _criar(conexao, "ensaio")
    proctor = _criar(conexao, "proctor", PROCTOR)

    # act
    copia = servico.duplicar_formulario(conexao, proctor.formulario.id, None, AGORA)

    # assert: a cópia referencia "ensaio" e registrou a dependência, como o original
    dependencias = listar_dependencias(conexao)
    assert (proctor.formulario.id, ensaio.formulario.id) in dependencias
    assert (copia.formulario.id, ensaio.formulario.id) in dependencias
    assert copia.versao.definicao == proctor.versao.definicao


def test_quem_depende_do_original_nao_passa_a_depender_da_copia(conexao):
    # arrange
    ensaio = _criar(conexao, "ensaio")
    proctor = _criar(conexao, "proctor", PROCTOR)

    # act
    copia = servico.duplicar_formulario(conexao, ensaio.formulario.id, None, AGORA)

    # assert: o proctor continua dependendo só do ensaio original
    assert [d for d in listar_dependencias(conexao) if d[0] == proctor.formulario.id] == [
        (proctor.formulario.id, ensaio.formulario.id)
    ]
    assert all(d[1] != copia.formulario.id for d in listar_dependencias(conexao))


def test_a_copia_da_origem_pode_ser_excluida_sem_afetar_o_original_com_dependentes(conexao):
    # arrange
    ensaio = _criar(conexao, "ensaio")
    _criar(conexao, "proctor", PROCTOR)
    copia = servico.duplicar_formulario(conexao, ensaio.formulario.id, None, AGORA)

    # act
    servico.excluir_formulario(conexao, copia.formulario.id)

    # assert: a cópia é independente; o original continua protegido por seu dependente
    with pytest.raises(ExclusaoBloqueada):
        servico.excluir_formulario(conexao, ensaio.formulario.id)
