from datetime import UTC, datetime

import pytest

from forms.dominio.models import (
    Campo,
    Definicao,
    DefinicaoInvalida,
    NaoEncontrado,
    TipoCampo,
)
from forms.infra import banco
from forms.infra.banco import Conexao
from forms.repositorios import formularios as repositorio
from forms.repositorios.formularios import (
    criar_formulario,
    excluir_formulario,
    inserir_versao,
    listar_formularios,
    listar_versoes,
    obter_formulario,
    obter_formulario_por_nome,
    obter_versao,
    obter_versao_atual,
)

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEPOIS = datetime(2026, 11, 3, 9, 30, 0, tzinfo=UTC)


def _definicao(*ids: str) -> Definicao:
    return Definicao(tuple(Campo(id=i, tipo=TipoCampo.TEXTO, rotulo=i.upper()) for i in ids))


# --- formulários ---


def test_criar_e_buscar_formulario(conexao: Conexao):
    # act
    criado = criar_formulario(conexao, "Ensaio", AGORA)

    # assert
    assert criado.nome == "Ensaio"
    assert criado.criado_em == "2026-11-02T10:00:00+00:00"
    assert obter_formulario(conexao, criado.id) == criado
    assert obter_formulario_por_nome(conexao, "Ensaio") == criado


def test_nome_e_guardado_sem_espacos_nas_pontas(conexao: Conexao):
    # act
    criado = criar_formulario(conexao, "  Ensaio  ", AGORA)

    # assert
    assert criado.nome == "Ensaio"


@pytest.mark.parametrize("repetido", ["ensaio", "ENSAIO", "  Ensaio ", "eNsAiO"])
def test_nome_repetido_com_outra_caixa_ou_espacos_e_erro_de_dominio(
    conexao: Conexao, repetido: str
):
    # arrange
    criar_formulario(conexao, "Ensaio", AGORA)

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        criar_formulario(conexao, repetido, AGORA)

    # assert: 422 no campo `nome` (AGENTS.md §2.2)
    assert [erro.campo for erro in excecao.value.erros] == ["nome"]
    assert "Já existe" in excecao.value.erros[0].mensagem


def test_nome_repetido_com_acento_em_forma_decomposta_tambem_e_repetido(
    conexao: Conexao,
):
    # arrange: "é" composto (U+00E9) e decomposto (e + U+0301) são o mesmo nome para quem lê
    criar_formulario(conexao, "Concreto Armado Té", AGORA)

    # act / assert
    with pytest.raises(DefinicaoInvalida):
        criar_formulario(conexao, "Concreto Armado Té", AGORA)


def test_nome_com_maiuscula_acentuada_e_comparado_sem_diferenciar_caixa(
    conexao: Conexao,
):
    # arrange: o `lower()` do SQLite só entende ASCII; a chave é calculada em Python
    criar_formulario(conexao, "Inspeção", AGORA)

    # act / assert
    with pytest.raises(DefinicaoInvalida):
        criar_formulario(conexao, "INSPEÇÃO".replace("Ã", "ã"), AGORA)


def test_nomes_diferentes_convivem(conexao: Conexao):
    # act
    criar_formulario(conexao, "Ensaio", AGORA)
    criar_formulario(conexao, "Proctor", AGORA)

    # assert
    assert [f.nome for f in listar_formularios(conexao)] == ["Ensaio", "Proctor"]


def test_formulario_inexistente_e_nao_encontrado(conexao: Conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        obter_formulario(conexao, 99)
    assert obter_formulario_por_nome(conexao, "Fantasma") is None


def test_buscar_por_nome_ignora_caixa_e_espacos(conexao: Conexao):
    # arrange
    criado = criar_formulario(conexao, "Ensaio", AGORA)

    # act / assert
    assert obter_formulario_por_nome(conexao, "  ENSAIO ") == criado


# --- versões ---


def test_primeira_versao_e_a_1_e_guarda_a_definicao_em_json(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)

    # act
    versao = inserir_versao(conexao, formulario.id, _definicao("a", "b"), AGORA)

    # assert
    assert versao.numero == 1 and versao.formulario_id == formulario.id
    assert versao.definicao == _definicao("a", "b")
    bruto = conexao.execute("SELECT definicao FROM versoes_formulario").fetchone()[0]
    assert bruto == {
        "campos": [
            {"id": "a", "tipo": "texto", "rotulo": "A"},
            {"id": "b", "tipo": "texto", "rotulo": "B"},
        ]
    }


def test_versao_atual_apos_duas_publicacoes_e_a_2(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    primeira = inserir_versao(conexao, formulario.id, _definicao("a"), AGORA)

    # act
    segunda = inserir_versao(conexao, formulario.id, _definicao("a", "b"), DEPOIS)

    # assert
    assert (primeira.numero, segunda.numero) == (1, 2)
    assert obter_versao_atual(conexao, formulario.id) == segunda
    assert obter_versao(conexao, primeira.id) == primeira


def test_numeracao_das_versoes_e_independente_por_formulario(conexao: Conexao):
    # arrange
    a = criar_formulario(conexao, "A", AGORA)
    b = criar_formulario(conexao, "B", AGORA)

    # act
    inserir_versao(conexao, a.id, _definicao("x"), AGORA)
    inserir_versao(conexao, a.id, _definicao("x"), AGORA)
    primeira_de_b = inserir_versao(conexao, b.id, _definicao("x"), AGORA)

    # assert
    assert primeira_de_b.numero == 1


def test_versao_antiga_continua_com_a_definicao_original(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    primeira = inserir_versao(conexao, formulario.id, _definicao("a"), AGORA)
    inserir_versao(conexao, formulario.id, _definicao("a", "b", "c"), DEPOIS)

    # act / assert
    assert obter_versao(conexao, primeira.id).definicao == _definicao("a")


def test_listar_versoes_traz_numero_e_data_sem_a_definicao(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    inserir_versao(conexao, formulario.id, _definicao("a"), AGORA)
    inserir_versao(conexao, formulario.id, _definicao("a"), DEPOIS)

    # act
    versoes = listar_versoes(conexao, formulario.id)

    # assert
    assert [(v.numero, v.publicada_em) for v in versoes] == [
        (1, "2026-11-02T10:00:00+00:00"),
        (2, "2026-11-03T09:30:00+00:00"),
    ]


def test_versao_de_outro_formulario_nao_e_encontrada_quando_se_informa_o_dono(
    conexao: Conexao,
):
    # arrange
    a = criar_formulario(conexao, "A", AGORA)
    b = criar_formulario(conexao, "B", AGORA)
    versao_de_a = inserir_versao(conexao, a.id, _definicao("x"), AGORA)

    # act / assert
    assert obter_versao(conexao, versao_de_a.id, formulario_id=a.id) == versao_de_a
    with pytest.raises(NaoEncontrado):
        obter_versao(conexao, versao_de_a.id, formulario_id=b.id)


def test_formulario_sem_versao_nao_tem_versao_atual(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)

    # act / assert
    with pytest.raises(NaoEncontrado):
        obter_versao_atual(conexao, formulario.id)


def test_versao_inexistente_e_nao_encontrada(conexao: Conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        obter_versao(conexao, 99)


def test_inserir_versao_em_formulario_inexistente_e_nao_encontrado(conexao: Conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        inserir_versao(conexao, 99, _definicao("a"), AGORA)


def test_o_modulo_nao_oferece_atualizar_nem_apagar_versao():
    # assert: versões publicadas são imutáveis (AGENTS.md §3.3)
    nomes = {nome for nome in dir(repositorio) if not nome.startswith("_")}
    assert not {
        n
        for n in nomes
        if "versao" in n and n.startswith(("atualizar", "editar", "excluir", "apagar", "remover"))
    }


# --- listagem ---


def test_listagem_traz_versao_atual_e_nao_traz_definicoes(conexao: Conexao):
    # arrange
    ensaio = criar_formulario(conexao, "Ensaio", AGORA)
    inserir_versao(conexao, ensaio.id, _definicao("a"), AGORA)
    segunda = inserir_versao(conexao, ensaio.id, _definicao("a"), DEPOIS)
    sem_versao = criar_formulario(conexao, "Rascunho", AGORA)

    # act
    resumos = {r.nome: r for r in listar_formularios(conexao)}

    # assert
    assert resumos["Ensaio"].versao_atual_id == segunda.id
    assert resumos["Ensaio"].versao_atual_numero == 2
    assert resumos["Rascunho"].id == sem_versao.id
    assert resumos["Rascunho"].versao_atual_id is None


# --- exclusão ---


def test_excluir_formulario_apaga_suas_versoes(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    inserir_versao(conexao, formulario.id, _definicao("a"), AGORA)

    # act
    excluir_formulario(conexao, formulario.id)

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM versoes_formulario").fetchone()[0] == 0
    with pytest.raises(NaoEncontrado):
        obter_formulario(conexao, formulario.id)


def test_excluir_formulario_inexistente_e_nao_encontrado(conexao: Conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        excluir_formulario(conexao, 99)


def test_nome_de_formulario_excluido_pode_ser_reutilizado(conexao: Conexao):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    excluir_formulario(conexao, formulario.id)

    # act / assert
    assert criar_formulario(conexao, "Ensaio", AGORA).nome == "Ensaio"


# --- segurança ---


def test_nome_com_aspas_e_sql_e_tratado_como_dado(conexao: Conexao):
    # arrange
    nome = "x'); DROP TABLE formularios; --"

    # act
    criado = criar_formulario(conexao, nome, AGORA)

    # assert
    assert obter_formulario(conexao, criado.id).nome == nome
    assert conexao.execute("SELECT COUNT(*) FROM formularios").fetchone()[0] == 1


def test_outra_conexao_da_mesma_equipe_enxerga_a_mesma_versao(conexao: Conexao, dsn: str):
    # arrange
    formulario = criar_formulario(conexao, "Ensaio", AGORA)
    inserida = inserir_versao(conexao, formulario.id, _definicao("a"), AGORA)
    segunda = banco.abrir_conexao(dsn)
    segunda.definir_contexto(conexao.contexto)

    # act / assert
    assert obter_versao_atual(segunda, formulario.id) == inserida
    segunda.close()
