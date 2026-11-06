"""Registros em equipe: autoria, histórico, concorrência, edição própria x alheia, avisos e
estado (AGENTS.md §2.3, §2.13, §2.14, §2.18)."""

import threading
from datetime import UTC, datetime, timedelta

import pytest

from forms.dominio.models import ConflitoDeRevisao, Contexto, NaoEncontrado, SemPermissao
from forms.infra import banco
from forms.infra.banco import Conexao
from forms.repositorios import equipes as repositorio_equipes
from forms.repositorios import formularios as repositorio
from forms.servicos import equipes as servico_equipes
from forms.servicos import servico

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEPOIS = AGORA + timedelta(hours=1)
DEFINICAO = {
    "campos": [
        {"id": "carga", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
        {"id": "limite", "tipo": "numero", "rotulo": "Limite"},
        {"id": "ok", "tipo": "calculado", "rotulo": "Conforme?", "formula": "carga >= limite"},
        {"id": "obs", "tipo": "texto", "rotulo": "Obs"},
    ]
}


@pytest.fixture
def formulario(conexao: Conexao):
    return servico.criar_formulario(conexao, "ensaio", DEFINICAO, AGORA)


def _como(conexao: Conexao, nome: str, permissoes: set[str]) -> int:
    """Passa a conexão para outra pessoa da mesma equipe, com as permissões dadas."""
    usuario = servico_equipes.identificar(conexao, f"sub-{nome}", nome.title(), None, AGORA)
    conexao.definir_contexto(Contexto(conexao.grupo_id, usuario.id, frozenset(permissoes)))
    return usuario.id


def _registro(conexao: Conexao, formulario, **dados: object):
    return servico.criar_registro(
        conexao, formulario.formulario.id, formulario.versao.id, {"limite": "10", **dados}, AGORA
    )


# --- autoria e histórico ---


def test_registro_guarda_quem_criou_e_quem_alterou(conexao: Conexao, formulario):
    # arrange
    autor = conexao.usuario_id
    registro = _registro(conexao, formulario, carga="12")

    # act
    editor = _como(conexao, "editor", {"registros:editar_todos"})
    editado = servico.atualizar_registro(
        conexao, registro.id, {"carga": "5", "limite": "10"}, DEPOIS
    )

    # assert
    assert (registro.criado_por, registro.atualizado_por) == (autor, autor)
    assert (editado.criado_por, editado.atualizado_por) == (autor, editor)


def test_cada_gravacao_deixa_uma_linha_de_historico_com_o_que_havia_antes(
    conexao: Conexao, formulario
):
    # arrange
    registro = _registro(conexao, formulario, carga="12")

    # act
    servico.atualizar_registro(conexao, registro.id, {"carga": "5", "limite": "10"}, DEPOIS)
    historico = servico.historico_do_registro(conexao, registro.id)

    # assert: do mais recente ao mais antigo
    assert [e.acao for e, _ in historico] == ["editado", "criado"]
    editado = historico[0][0]
    assert editado.valores_anteriores["carga"] == "12"
    assert editado.quando == "2026-11-02T11:00:00+00:00"
    assert historico[1][0].valores_anteriores is None


def test_historico_sobrevive_a_exclusao_do_registro(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario, carga="12")

    # act
    servico.excluir_registro(conexao, registro.id, DEPOIS)

    # assert
    acoes = [e.acao for e, _ in servico.historico_do_registro(conexao, registro.id)]
    assert acoes == ["excluido", "criado"]
    with pytest.raises(NaoEncontrado):
        servico.obter_registro(conexao, registro.id)


def test_historico_de_registro_que_nunca_existiu_e_nao_encontrado(conexao: Conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.historico_do_registro(conexao, 999)


def test_historico_mostra_o_nome_de_quem_fez(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario)

    # act
    historico = servico.historico_do_registro(conexao, registro.id)

    # assert
    assert historico[0][1] == "Pessoa de Teste"


# --- concorrência otimista ---


def test_cada_gravacao_incrementa_a_revisao(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario)

    # act
    editado = servico.atualizar_registro(conexao, registro.id, {"limite": "9"}, DEPOIS)

    # assert
    assert (registro.revisao, editado.revisao) == (1, 2)


def test_edicao_com_revisao_antiga_e_conflito_e_nada_e_gravado(conexao: Conexao, formulario):
    # arrange: duas pessoas leram a revisão 1; a primeira salva
    registro = _registro(conexao, formulario, carga="1")
    _como(conexao, "bia", {"registros:editar_todos"})
    servico.atualizar_registro(conexao, registro.id, {"carga": "2", "limite": "10"}, DEPOIS, 1)

    # act / assert: a segunda tenta salvar em cima, com a revisão que leu
    with pytest.raises(ConflitoDeRevisao, match="Bia alterou"):
        servico.atualizar_registro(conexao, registro.id, {"carga": "3", "limite": "10"}, DEPOIS, 1)
    assert servico.obter_registro(conexao, registro.id).dados["carga"] == "2"
    assert len(servico.historico_do_registro(conexao, registro.id)) == 2  # criado + 1 edição


def test_edicao_com_a_revisao_certa_passa(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario)

    # act
    editado = servico.atualizar_registro(conexao, registro.id, {"limite": "9"}, DEPOIS, 1)

    # assert
    assert editado.revisao == 2


def test_duas_edicoes_simultaneas_com_a_mesma_revisao_so_uma_vence(
    conexao: Conexao, formulario, dsn: str
):
    # arrange
    registro = _registro(conexao, formulario)
    resultados: list[str] = []
    barreira = threading.Barrier(2)

    def editar(valor: str) -> None:
        outra = banco.abrir_conexao(dsn)
        outra.definir_contexto(conexao.contexto)
        barreira.wait()
        try:
            servico.atualizar_registro(outra, registro.id, {"limite": valor}, DEPOIS, 1)
            resultados.append("ok")
        except ConflitoDeRevisao:
            resultados.append("conflito")
        finally:
            outra.close()

    # act
    threads = [threading.Thread(target=editar, args=(v,)) for v in ("7", "8")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # assert
    assert sorted(resultados) == ["conflito", "ok"]
    assert servico.obter_registro(conexao, registro.id).revisao == 2


# --- editar os próprios x os de outras pessoas ---


def test_tecnico_edita_o_que_criou_mas_nao_o_de_outra_pessoa(conexao: Conexao, formulario):
    # arrange
    do_admin = _registro(conexao, formulario)
    _como(conexao, "tec", {"registros:criar", "registros:editar_proprios", "registros:ver"})
    proprio = _registro(conexao, formulario)

    # act
    editado = servico.atualizar_registro(conexao, proprio.id, {"limite": "1"}, DEPOIS)

    # assert
    assert editado.revisao == 2
    with pytest.raises(SemPermissao):
        servico.atualizar_registro(conexao, do_admin.id, {"limite": "1"}, DEPOIS)


def test_quem_pode_editar_todos_edita_o_de_qualquer_pessoa(conexao: Conexao, formulario):
    # arrange
    do_admin = _registro(conexao, formulario)
    _como(conexao, "eng", {"registros:editar_todos"})

    # act / assert
    assert servico.atualizar_registro(conexao, do_admin.id, {"limite": "1"}, DEPOIS).revisao == 2


def test_sem_nenhuma_permissao_de_edicao_nada_se_edita(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario)
    _como(conexao, "leitor", {"registros:ver"})

    # act / assert
    with pytest.raises(SemPermissao):
        servico.atualizar_registro(conexao, registro.id, {"limite": "1"}, DEPOIS)


def test_excluir_exige_a_permissao_de_excluir(conexao: Conexao, formulario):
    # arrange
    registro = _registro(conexao, formulario)
    _como(conexao, "eng", {"registros:editar_todos"})

    # act / assert
    with pytest.raises(SemPermissao):
        servico.excluir_registro(conexao, registro.id, DEPOIS)


# --- avisos ---


def test_quem_criou_e_avisado_quando_outra_pessoa_edita_mas_nao_ao_editar_o_proprio(
    conexao: Conexao, formulario
):
    # arrange
    autor = conexao.usuario_id
    registro = _registro(conexao, formulario)
    servico.atualizar_registro(conexao, registro.id, {"limite": "9"}, DEPOIS)  # o próprio autor
    _como(conexao, "outra", {"registros:editar_todos"})

    # act
    servico.atualizar_registro(conexao, registro.id, {"limite": "8"}, DEPOIS)

    # assert
    conexao.definir_contexto(Contexto(conexao.grupo_id, autor, frozenset()))
    itens, nao_lidas = servico.listar_notificacoes(conexao)
    assert [n.tipo for n in itens] == ["registro_editado"] and nao_lidas == 1
    assert itens[0].referencia == {"registro_id": registro.id}


def test_notificacao_lida_deixa_de_contar_e_so_a_dona_marca(conexao: Conexao, formulario):
    # arrange
    autor = conexao.usuario_id
    registro = _registro(conexao, formulario)
    _como(conexao, "outra", {"registros:editar_todos"})
    servico.atualizar_registro(conexao, registro.id, {"limite": "8"}, DEPOIS)
    conexao.definir_contexto(Contexto(conexao.grupo_id, autor, frozenset()))
    notificacao = servico.listar_notificacoes(conexao)[0][0]

    # act
    servico.marcar_notificacao_lida(conexao, notificacao.id, DEPOIS)

    # assert
    assert servico.listar_notificacoes(conexao)[1] == 0
    _como(conexao, "intrusa", set())
    with pytest.raises(NaoEncontrado):
        servico.marcar_notificacao_lida(conexao, notificacao.id, DEPOIS)


# --- cascata: histórico e aviso de erro ---

ORIGEM = {"campos": [{"id": "div", "tipo": "numero", "rotulo": "Divisor", "compartilhado": True}]}
DEPENDENTE = {
    "campos": [
        {
            "id": "o",
            "tipo": "referencia",
            "rotulo": "O",
            "formulario": "origem",
            "obrigatorio": True,
        },
        {"id": "r", "tipo": "calculado", "rotulo": "R", "formula": "10 / o__div"},
    ]
}


@pytest.fixture
def cadeia(conexao: Conexao):
    origem = servico.criar_formulario(conexao, "origem", ORIGEM, AGORA)
    dependente = servico.criar_formulario(conexao, "dependente", DEPENDENTE, AGORA)
    return origem, dependente


def test_cascata_registra_historico_com_o_motivo_e_avisa_o_dono_do_erro(conexao: Conexao, cadeia):
    # arrange: a origem é de uma pessoa; o dependente, de outra
    origem, dependente = cadeia
    dono_da_origem = conexao.usuario_id
    reg_origem = servico.criar_registro(
        conexao, origem.formulario.id, origem.versao.id, {"div": "2"}, AGORA
    )
    dono_do_dependente = _como(conexao, "dona", {"registros:criar"})
    reg_dep = servico.criar_registro(
        conexao, dependente.formulario.id, dependente.versao.id, {"o": reg_origem.id}, AGORA
    )
    conexao.definir_contexto(
        Contexto(conexao.grupo_id, dono_da_origem, frozenset({"registros:editar_todos"}))
    )

    # act: dividir por zero na origem estoura o cálculo do dependente
    servico.atualizar_registro(conexao, reg_origem.id, {"div": "0"}, DEPOIS)

    # assert
    atual = servico.obter_registro(conexao, reg_dep.id)
    assert atual.dados["r"]["erro"] == "Divisão por zero."
    historico = servico.historico_do_registro(conexao, reg_dep.id)
    assert historico[0][0].acao == "recalculado"
    assert historico[0][0].motivo == f"recalculado por alteração em #{reg_origem.id}"
    conexao.definir_contexto(Contexto(conexao.grupo_id, dono_do_dependente, frozenset()))
    tipos = [n.tipo for n in servico.listar_notificacoes(conexao)[0]]
    assert "erro_em_cascata" in tipos


def test_cascata_que_nao_muda_nada_nao_gera_historico(conexao: Conexao, cadeia):
    # arrange
    origem, dependente = cadeia
    reg_origem = servico.criar_registro(
        conexao, origem.formulario.id, origem.versao.id, {"div": "2"}, AGORA
    )
    reg_dep = servico.criar_registro(
        conexao, dependente.formulario.id, dependente.versao.id, {"o": reg_origem.id}, AGORA
    )

    # act: edita a origem sem mudar o que o dependente usa
    servico.atualizar_registro(conexao, reg_origem.id, {"div": "2.0"}, DEPOIS)

    # assert
    assert [e.acao for e, _ in servico.historico_do_registro(conexao, reg_dep.id)] == ["criado"]


# --- anonimização ao excluir a conta ---


def test_excluir_a_conta_anonimiza_a_autoria_e_mantem_o_registro(conexao: Conexao, formulario):
    # arrange
    autora = _como(conexao, "saindo", {"registros:criar", "registros:ver"})
    registro = _registro(conexao, formulario)

    # act
    repositorio_equipes.apagar_usuario(conexao, autora)

    # assert
    atual = repositorio.obter_registro(conexao, registro.id)
    assert atual.criado_por is None and atual.atualizado_por is None
    historico = servico.historico_do_registro(conexao, registro.id)
    assert historico[0][0].usuario_id is None and historico[0][1] is None


# --- listagem: só os meus; estado; contagens ---


def test_listagem_so_dos_meus_registros(conexao: Conexao, formulario):
    # arrange
    meu = _registro(conexao, formulario)
    _como(conexao, "outra", {"registros:criar"})
    _registro(conexao, formulario)
    conexao.definir_contexto(Contexto(conexao.grupo_id, meu.criado_por, frozenset()))

    # act
    todos = servico.listar_registros(conexao, formulario.formulario.id)
    meus = servico.listar_registros(conexao, formulario.formulario.id, meus=True)

    # assert
    assert todos.total == 2 and [r.id for r in meus.itens] == [meu.id]


def test_contagens_por_estado_decididas_no_servidor(conexao: Conexao, formulario):
    # arrange: conforme, não conforme e aguardando (sem carga)
    _registro(conexao, formulario, carga="12")
    _registro(conexao, formulario, carga="3")
    _registro(conexao, formulario)

    # act
    contagens = servico.contar_por_estado(conexao, formulario.formulario.id)

    # assert
    assert contagens.campo_status == "ok"
    assert (contagens.total, contagens.conforme, contagens.nao_conforme) == (3, 1, 1)
    assert (contagens.erro, contagens.aguardando) == (0, 1)


def test_contagens_respeitam_os_filtros_da_listagem(conexao: Conexao, formulario):
    # arrange
    _registro(conexao, formulario, carga="12", obs="a")
    _registro(conexao, formulario, carga="12", obs="b")

    # act
    contagens = servico.contar_por_estado(conexao, formulario.formulario.id, filtros={"obs": "a"})

    # assert
    assert contagens.total == 1 and contagens.conforme == 1


def test_formulario_sem_campo_de_status_conta_tudo_como_aguardando(conexao: Conexao):
    # arrange
    criado = servico.criar_formulario(
        conexao, "simples", {"campos": [{"id": "a", "tipo": "texto", "rotulo": "A"}]}, AGORA
    )
    servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, {"a": "x"}, AGORA)

    # act
    contagens = servico.contar_por_estado(conexao, criado.formulario.id)

    # assert
    assert contagens.campo_status is None and (contagens.total, contagens.aguardando) == (1, 1)


def test_exibicao_declarada_vale_sobre_o_padrao(conexao: Conexao):
    # arrange
    definicao = {
        "campos": [
            {"id": "a", "tipo": "numero", "rotulo": "A"},
            {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "a * 2"},
            {"id": "triplo", "tipo": "calculado", "rotulo": "Triplo", "formula": "a * 3"},
            {"id": "p1", "tipo": "calculado", "rotulo": "P1", "formula": "a > 1"},
            {"id": "p2", "tipo": "calculado", "rotulo": "P2", "formula": "a > 2"},
        ],
        "exibicao": {"destaque": "triplo", "status": "p2"},
    }
    criado = servico.criar_formulario(conexao, "x", definicao, AGORA)
    servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, {"a": "3"}, AGORA)

    # act
    listagem = servico.listar_registros(conexao, criado.formulario.id)

    # assert: sem `exibicao` o padrão seria dobro e p1
    assert listagem.exibicao.destaque == "triplo" and listagem.campo_status == "p2"
    assert servico.estado_do_registro(listagem.itens[0].dados, listagem.campo_status) == "conforme"


@pytest.mark.parametrize(
    ("dados", "estado"),
    [
        ({"ok": {"valor": True, "erro": None}}, "conforme"),
        ({"ok": {"valor": False, "erro": None}}, "nao_conforme"),
        ({"ok": {"valor": None, "erro": None}}, "aguardando"),
        ({"ok": {"valor": None, "erro": "Divisão por zero."}}, "erro"),
        ({}, "aguardando"),
    ],
)
def test_estado_do_registro_cobre_os_quatro_casos(dados, estado):
    # act / assert
    assert servico.estado_do_registro(dados, "ok") == estado
    assert servico.estado_do_registro(dados, None) == "sem_status"
