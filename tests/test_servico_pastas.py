import sqlite3
from datetime import UTC, datetime

import pytest

from forms import servico
from forms.models import ExclusaoBloqueada, NaoEncontrado, PastaInvalida
from forms.repositorio import abrir_conexao

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEFINICAO = {"campos": [{"id": "obs", "tipo": "texto", "rotulo": "Observação"}]}


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


def _formulario(conexao: sqlite3.Connection, nome: str = "ensaio") -> int:
    return servico.criar_formulario(conexao, nome, DEFINICAO, AGORA).formulario.id


def _erros(excecao: pytest.ExceptionInfo[PastaInvalida]) -> list[tuple[str, str]]:
    return [(erro.campo, erro.mensagem) for erro in excecao.value.erros]


# --- criar e listar ---


def test_cria_pasta_na_raiz_e_subpasta(conexao):
    # act
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    fundacao = servico.criar_pasta(conexao, "Fundação", obras.id, AGORA)

    # assert
    assert (obras.nome, obras.pasta_pai_id) == ("Obras", None)
    assert (fundacao.nome, fundacao.pasta_pai_id) == ("Fundação", obras.id)
    assert obras.criado_em == "2026-11-02T10:00:00+00:00"


def test_lista_as_pastas_em_lista_plana_na_ordem_de_criacao(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    fundacao = servico.criar_pasta(conexao, "Fundação", obras.id, AGORA)

    # act
    pastas = servico.listar_pastas(conexao)

    # assert
    assert [(p.id, p.nome, p.pasta_pai_id) for p in pastas] == [
        (obras.id, "Obras", None),
        (fundacao.id, "Fundação", obras.id),
    ]


def test_nome_da_pasta_perde_os_espacos_das_pontas(conexao):
    # act
    pasta = servico.criar_pasta(conexao, "  Obras  ", None, AGORA)

    # assert
    assert pasta.nome == "Obras"


def test_pasta_sem_nome_e_recusada_no_campo_nome(conexao):
    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.criar_pasta(conexao, "   ", None, AGORA)

    # assert
    assert _erros(erro) == [("nome", "O nome da pasta é obrigatório.")]


def test_pasta_pai_inexistente_e_recusada_no_campo_pasta_pai_id(conexao):
    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.criar_pasta(conexao, "Obras", 99, AGORA)

    # assert
    assert _erros(erro) == [("pasta_pai_id", "A pasta de destino não existe.")]


# --- unicidade do nome entre irmãs ---


@pytest.mark.parametrize("repetido", ["Obras", "  obras ", "OBRAS"])
def test_nome_repetido_na_raiz_e_recusado_sem_diferenciar_caixa_nem_espacos(conexao, repetido):
    # arrange
    servico.criar_pasta(conexao, "Obras", None, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.criar_pasta(conexao, repetido, None, AGORA)

    # assert
    assert _erros(erro) == [("nome", "Já existe uma pasta com este nome neste local.")]


def test_nome_repetido_dentro_da_mesma_pasta_pai_e_recusado(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    servico.criar_pasta(conexao, "Fundação", obras.id, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.criar_pasta(conexao, "fundação", obras.id, AGORA)

    # assert
    assert _erros(erro) == [("nome", "Já existe uma pasta com este nome neste local.")]


def test_mesmo_nome_em_pastas_pai_diferentes_e_permitido(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    lab = servico.criar_pasta(conexao, "Laboratório", None, AGORA)

    # act
    servico.criar_pasta(conexao, "2026", obras.id, AGORA)
    servico.criar_pasta(conexao, "2026", lab.id, AGORA)

    # assert
    assert [p.nome for p in servico.listar_pastas(conexao)].count("2026") == 2


# --- renomear e mover ---


def test_renomeia_a_pasta_sem_mudar_o_local(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    fundacao = servico.criar_pasta(conexao, "Fundação", obras.id, AGORA)

    # act
    pasta = servico.atualizar_pasta(conexao, fundacao.id, "Estacas", obras.id)

    # assert
    assert (pasta.nome, pasta.pasta_pai_id) == ("Estacas", obras.id)


def test_manter_o_proprio_nome_nao_conta_como_repetido(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)

    # act: só troca a caixa do próprio nome
    pasta = servico.atualizar_pasta(conexao, obras.id, "OBRAS", None)

    # assert
    assert pasta.nome == "OBRAS"


def test_move_a_pasta_para_outra_e_de_volta_para_a_raiz(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    lab = servico.criar_pasta(conexao, "Laboratório", None, AGORA)
    ensaios = servico.criar_pasta(conexao, "Ensaios", obras.id, AGORA)

    # act
    movida = servico.atualizar_pasta(conexao, ensaios.id, "Ensaios", lab.id)
    na_raiz = servico.atualizar_pasta(conexao, ensaios.id, "Ensaios", None)

    # assert
    assert movida.pasta_pai_id == lab.id
    assert na_raiz.pasta_pai_id is None


def test_mover_para_o_destino_com_nome_igual_e_recusado(conexao):
    # arrange: já existe "Ensaios" na raiz, e a outra "Ensaios" tenta ir para lá
    servico.criar_pasta(conexao, "Ensaios", None, AGORA)
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    ensaios = servico.criar_pasta(conexao, "Ensaios", obras.id, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.atualizar_pasta(conexao, ensaios.id, "Ensaios", None)

    # assert
    assert _erros(erro) == [("nome", "Já existe uma pasta com este nome neste local.")]


def test_mover_a_pasta_para_dentro_dela_mesma_e_recusado(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.atualizar_pasta(conexao, obras.id, "Obras", obras.id)

    # assert
    assert _erros(erro) == [
        ("pasta_pai_id", "Uma pasta não pode ser movida para dentro dela mesma ou de uma subpasta.")
    ]


def test_mover_a_pasta_para_uma_descendente_distante_e_recusado(conexao):
    # arrange: a > b > c, e tentar pôr "a" dentro de "c"
    a = servico.criar_pasta(conexao, "a", None, AGORA)
    b = servico.criar_pasta(conexao, "b", a.id, AGORA)
    c = servico.criar_pasta(conexao, "c", b.id, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.atualizar_pasta(conexao, a.id, "a", c.id)

    # assert: nada mudou
    assert _erros(erro)[0][0] == "pasta_pai_id"
    assert next(p for p in servico.listar_pastas(conexao) if p.id == a.id).pasta_pai_id is None


def test_atualizar_pasta_inexistente_levanta_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.atualizar_pasta(conexao, 99, "x", None)


def test_atualizar_com_pai_inexistente_e_recusado_no_campo(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.atualizar_pasta(conexao, obras.id, "Obras", 99)

    # assert
    assert _erros(erro) == [("pasta_pai_id", "A pasta de destino não existe.")]


# --- excluir ---


def test_exclui_pasta_vazia(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)

    # act
    servico.excluir_pasta(conexao, obras.id)

    # assert
    assert servico.listar_pastas(conexao) == []


def test_excluir_pasta_com_subpasta_e_bloqueado(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    servico.criar_pasta(conexao, "Fundação", obras.id, AGORA)

    # act
    with pytest.raises(ExclusaoBloqueada, match="subpasta"):
        servico.excluir_pasta(conexao, obras.id)

    # assert: nada em cascata
    assert len(servico.listar_pastas(conexao)) == 2


def test_excluir_pasta_com_formulario_e_bloqueado(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    formulario_id = _formulario(conexao)
    servico.mover_formulario(conexao, formulario_id, obras.id)

    # act
    with pytest.raises(ExclusaoBloqueada, match="formulário"):
        servico.excluir_pasta(conexao, obras.id)

    # assert
    assert servico.obter_formulario(conexao, formulario_id).formulario.pasta_id == obras.id


def test_excluir_pasta_inexistente_levanta_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.excluir_pasta(conexao, 99)


def test_depois_de_esvaziar_a_pasta_ela_pode_ser_excluida(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    formulario_id = _formulario(conexao)
    servico.mover_formulario(conexao, formulario_id, obras.id)
    servico.mover_formulario(conexao, formulario_id, None)

    # act
    servico.excluir_pasta(conexao, obras.id)

    # assert
    assert servico.listar_pastas(conexao) == []


# --- mover formulário ---


def test_formulario_novo_fica_na_raiz(conexao):
    # act
    formulario_id = _formulario(conexao)

    # assert
    assert servico.obter_formulario(conexao, formulario_id).formulario.pasta_id is None


def test_move_o_formulario_para_a_pasta_e_de_volta_para_a_raiz(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    formulario_id = _formulario(conexao)

    # act
    servico.mover_formulario(conexao, formulario_id, obras.id)
    dentro = servico.obter_formulario(conexao, formulario_id).formulario.pasta_id
    servico.mover_formulario(conexao, formulario_id, None)
    fora = servico.obter_formulario(conexao, formulario_id).formulario.pasta_id

    # assert
    assert (dentro, fora) == (obras.id, None)


def test_listagem_de_formularios_traz_a_pasta_de_cada_um(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    dentro = _formulario(conexao, "dentro")
    _formulario(conexao, "fora")
    servico.mover_formulario(conexao, dentro, obras.id)

    # act
    resumos = {f.nome: f.pasta_id for f in servico.listar_formularios(conexao)}

    # assert
    assert resumos == {"dentro": obras.id, "fora": None}


def test_mover_formulario_para_pasta_inexistente_e_recusado_no_campo(conexao):
    # arrange
    formulario_id = _formulario(conexao)

    # act
    with pytest.raises(PastaInvalida) as erro:
        servico.mover_formulario(conexao, formulario_id, 99)

    # assert
    assert _erros(erro) == [("pasta_id", "A pasta de destino não existe.")]


def test_mover_formulario_inexistente_levanta_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.mover_formulario(conexao, 99, None)


def test_mover_formulario_nao_mexe_em_versoes_nem_registros(conexao):
    # arrange
    obras = servico.criar_pasta(conexao, "Obras", None, AGORA)
    criado = servico.criar_formulario(conexao, "ensaio", DEFINICAO, AGORA)
    registro = servico.criar_registro(
        conexao, criado.formulario.id, criado.versao.id, {"obs": "ok"}, AGORA
    )

    # act
    servico.mover_formulario(conexao, criado.formulario.id, obras.id)

    # assert: o registro continua apontando para a mesma versão e o formulário não ganha versão
    assert servico.obter_registro(conexao, registro.id).versao_id == criado.versao.id
    assert [v.numero for v in servico.listar_versoes(conexao, criado.formulario.id)] == [1]
