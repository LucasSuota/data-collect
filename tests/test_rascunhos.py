"""Rascunho de versão (AGENTS.md §2.2): salvar incompleto, concorrência e publicar."""

from datetime import UTC, datetime

import pytest

from forms.dominio.models import ConflitoDeRevisao, DefinicaoInvalida, NaoEncontrado, ValorInvalido
from forms.infra.banco import Conexao
from forms.servicos import servico

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
V1 = {"campos": [{"id": "a", "tipo": "texto", "rotulo": "A"}]}
V2 = {
    "campos": [
        {"id": "a", "tipo": "texto", "rotulo": "A"},
        {"id": "b", "tipo": "numero", "rotulo": "B"},
    ]
}
INCOMPLETO = {
    "campos": [{"id": "x", "tipo": "calculado", "rotulo": "X", "formula": "fantasma + 1"}]
}


@pytest.fixture
def formulario(conexao: Conexao):
    return servico.criar_formulario(conexao, "ensaio", V1, AGORA).formulario


# --- serviço ---


def test_formulario_sem_rascunho_responde_nao_encontrado(conexao, formulario):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.obter_rascunho(conexao, formulario.id)


def test_criar_o_rascunho_guarda_a_versao_de_origem_e_comeca_na_revisao_1(conexao, formulario):
    # act
    rascunho = servico.salvar_rascunho(conexao, formulario.id, V2, None, AGORA)

    # assert
    assert rascunho.revisao == 1 and rascunho.definicao == V2
    assert (
        rascunho.base_versao_id == servico.obter_formulario(conexao, formulario.id).versao_atual.id
    )
    assert rascunho.atualizado_por == conexao.usuario_id


def test_rascunho_aceita_definicao_incompleta_como_o_validar(conexao, formulario):
    # act
    rascunho = servico.salvar_rascunho(conexao, formulario.id, INCOMPLETO, None, AGORA)

    # assert: salva sem validar; só publicar recusa
    assert rascunho.definicao == INCOMPLETO


def test_substituir_exige_a_revisao_lida_e_incrementa(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, V1, None, AGORA)

    # act
    novo = servico.salvar_rascunho(conexao, formulario.id, V2, 1, AGORA)

    # assert
    assert novo.revisao == 2 and novo.definicao == V2


def test_revisao_antiga_ou_ausente_ao_substituir_e_conflito(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, V1, None, AGORA)
    servico.salvar_rascunho(conexao, formulario.id, V2, 1, AGORA)

    # act / assert
    with pytest.raises(ConflitoDeRevisao):
        servico.salvar_rascunho(conexao, formulario.id, V1, 1, AGORA)
    with pytest.raises(ConflitoDeRevisao):
        servico.salvar_rascunho(conexao, formulario.id, V1, None, AGORA)
    assert servico.obter_rascunho(conexao, formulario.id).definicao == V2


def test_revisao_de_rascunho_que_nao_existe_mais_e_nao_encontrado(conexao, formulario):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.salvar_rascunho(conexao, formulario.id, V1, 3, AGORA)


@pytest.mark.parametrize("definicao", [[], "texto", 5, None])
def test_rascunho_que_nao_e_objeto_e_recusado(conexao, formulario, definicao):
    # act / assert
    with pytest.raises(ValorInvalido):
        servico.salvar_rascunho(conexao, formulario.id, definicao, None, AGORA)


def test_rascunho_gigante_e_recusado(conexao, formulario):
    # arrange
    enorme = {"campos": [{"id": f"c{i}", "tipo": "texto", "rotulo": "C"} for i in range(501)]}

    # act / assert
    with pytest.raises(ValorInvalido, match="campos demais"):
        servico.salvar_rascunho(conexao, formulario.id, enorme, None, AGORA)


def test_descartar_apaga_e_descartar_de_novo_e_nao_encontrado(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, V2, None, AGORA)

    # act
    servico.descartar_rascunho(conexao, formulario.id)

    # assert
    with pytest.raises(NaoEncontrado):
        servico.obter_rascunho(conexao, formulario.id)
    with pytest.raises(NaoEncontrado):
        servico.descartar_rascunho(conexao, formulario.id)


def test_publicar_cria_a_versao_seguinte_e_remove_o_rascunho(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, V2, None, AGORA)

    # act
    versao = servico.publicar_rascunho(conexao, formulario.id, AGORA)

    # assert
    assert versao.numero == 2 and len(versao.definicao.campos) == 2
    with pytest.raises(NaoEncontrado):
        servico.obter_rascunho(conexao, formulario.id)
    assert servico.obter_versao(conexao, formulario.id, versao.id).numero == 2


def test_publicar_rascunho_invalido_recusa_com_os_erros_e_o_rascunho_continua(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, INCOMPLETO, None, AGORA)

    # act / assert
    with pytest.raises(DefinicaoInvalida) as erro:
        servico.publicar_rascunho(conexao, formulario.id, AGORA)
    assert erro.value.erros[0].campo == "x.formula"
    assert servico.obter_rascunho(conexao, formulario.id).definicao == INCOMPLETO
    assert [v.numero for v in servico.listar_versoes(conexao, formulario.id)] == [1]


def test_publicar_sem_rascunho_e_nao_encontrado(conexao, formulario):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.publicar_rascunho(conexao, formulario.id, AGORA)


def test_rascunho_de_formulario_excluido_some_junto(conexao, formulario):
    # arrange
    servico.salvar_rascunho(conexao, formulario.id, V2, None, AGORA)

    # act
    servico.excluir_formulario(conexao, formulario.id)

    # assert
    assert conexao.execute("SELECT COUNT(*) AS n FROM rascunhos_formulario").fetchone()["n"] == 0


# --- API ---


def test_api_do_rascunho_do_primeiro_salvamento_a_publicacao(cliente):
    # arrange
    f = cliente.post("/formularios", json={"nome": "ensaio", "definicao": V1}).json()
    base = f"/formularios/{f['id']}/rascunho"
    assert cliente.get(base).status_code == 404

    # act
    criado = cliente.put(base, json={"definicao": V2})
    editado = cliente.put(base, json={"definicao": V2, "revisao": 1})
    publicado = cliente.post(f"{base}/publicar")

    # assert
    assert criado.status_code == 200 and criado.json()["revisao"] == 1
    assert criado.json()["atualizado_por"]["nome"] == "ana"
    assert editado.json()["revisao"] == 2
    assert publicado.status_code == 201 and publicado.json()["numero"] == 2
    assert cliente.get(base).status_code == 404


def test_api_do_rascunho_conflito_e_409_com_codigo(cliente):
    # arrange
    f = cliente.post("/formularios", json={"nome": "ensaio", "definicao": V1}).json()
    base = f"/formularios/{f['id']}/rascunho"
    cliente.put(base, json={"definicao": V1})
    cliente.put(base, json={"definicao": V2, "revisao": 1})

    # act
    conflito = cliente.put(base, json={"definicao": V1, "revisao": 1})

    # assert
    assert conflito.status_code == 409 and conflito.json()["codigo"] == "revisao_desatualizada"


def test_api_publicar_rascunho_invalido_e_422_localizado(cliente):
    # arrange
    f = cliente.post("/formularios", json={"nome": "ensaio", "definicao": V1}).json()
    base = f"/formularios/{f['id']}/rascunho"
    cliente.put(base, json={"definicao": INCOMPLETO})

    # act
    resposta = cliente.post(f"{base}/publicar")

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "x.formula"
    assert cliente.get(base).status_code == 200


def test_api_rascunho_de_formulario_inexistente_e_404_e_descartar_devolve_204(cliente):
    # arrange
    f = cliente.post("/formularios", json={"nome": "ensaio", "definicao": V1}).json()
    cliente.put(f"/formularios/{f['id']}/rascunho", json={"definicao": V2})

    # act / assert
    assert cliente.get("/formularios/999/rascunho").status_code == 404
    assert cliente.delete(f"/formularios/{f['id']}/rascunho").status_code == 204
    assert cliente.delete(f"/formularios/{f['id']}/rascunho").status_code == 404
