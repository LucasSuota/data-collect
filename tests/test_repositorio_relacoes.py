from datetime import UTC, datetime

import psycopg
import pytest

from forms.dominio.models import Campo, Definicao, TipoCampo
from forms.infra.banco import Conexao
from forms.repositorios.formularios import (
    criar_formulario,
    formularios_dependentes,
    inserir_registro,
    inserir_versao,
    listar_dependencias,
    obter_referencias,
    registrar_dependencias,
    registros_dependentes,
    registros_que_referenciam,
    substituir_referencias,
)

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEFINICAO = Definicao((Campo(id="a", tipo=TipoCampo.TEXTO, rotulo="A"),))


def _formulario(conexao: Conexao, nome: str):
    formulario = criar_formulario(conexao, nome, AGORA)
    versao = inserir_versao(conexao, formulario.id, DEFINICAO, AGORA)
    return formulario, versao


def _registro(conexao, versao) -> int:
    return inserir_registro(conexao, versao.formulario_id, versao.id, {}, AGORA).id


# --- dependências entre formulários ---


def test_dependencia_direta_e_transitiva_entre_formularios(conexao):
    # arrange: insitu -> proctor -> ensaio
    ensaio, _ = _formulario(conexao, "ensaio")
    proctor, _ = _formulario(conexao, "proctor")
    insitu, _ = _formulario(conexao, "insitu")
    registrar_dependencias(conexao, proctor.id, [ensaio.id])
    registrar_dependencias(conexao, insitu.id, [proctor.id])

    # act / assert
    assert formularios_dependentes(conexao, ensaio.id, transitivo=False) == [proctor.id]
    assert formularios_dependentes(conexao, ensaio.id, transitivo=True) == [proctor.id, insitu.id]
    assert formularios_dependentes(conexao, insitu.id, transitivo=True) == []


def test_registrar_a_mesma_dependencia_duas_vezes_nao_duplica(conexao):
    # arrange
    ensaio, _ = _formulario(conexao, "ensaio")
    proctor, _ = _formulario(conexao, "proctor")

    # act
    registrar_dependencias(conexao, proctor.id, [ensaio.id])
    registrar_dependencias(conexao, proctor.id, [ensaio.id])

    # assert
    assert listar_dependencias(conexao) == [(proctor.id, ensaio.id)]


def test_dependencia_permanece_depois_de_nova_versao(conexao):
    # arrange: o vínculo vale enquanto o formulário existir (versões antigas ainda apontam)
    ensaio, _ = _formulario(conexao, "ensaio")
    proctor, _ = _formulario(conexao, "proctor")
    registrar_dependencias(conexao, proctor.id, [ensaio.id])

    # act
    inserir_versao(conexao, proctor.id, DEFINICAO, AGORA)

    # assert
    assert formularios_dependentes(conexao, ensaio.id, transitivo=False) == [proctor.id]


def test_formulario_com_varios_dependentes_e_diamante(conexao):
    # arrange: b e c dependem de a; d depende de b e c
    a, _ = _formulario(conexao, "a")
    b, _ = _formulario(conexao, "b")
    c, _ = _formulario(conexao, "c")
    d, _ = _formulario(conexao, "d")
    registrar_dependencias(conexao, b.id, [a.id])
    registrar_dependencias(conexao, c.id, [a.id])
    registrar_dependencias(conexao, d.id, [b.id, c.id])

    # act
    transitivos = formularios_dependentes(conexao, a.id, transitivo=True)

    # assert: sem repetir d
    assert sorted(transitivos) == sorted([b.id, c.id, d.id]) and len(transitivos) == 3


# --- referências entre registros ---


def test_registro_referenciado_por_varios_dependentes(conexao):
    # arrange
    _, v_ensaio = _formulario(conexao, "ensaio")
    _, v_proctor = _formulario(conexao, "proctor")
    origem = _registro(conexao, v_ensaio)
    p1, p2 = _registro(conexao, v_proctor), _registro(conexao, v_proctor)

    # act
    substituir_referencias(conexao, p1, {"ensaio": origem})
    substituir_referencias(conexao, p2, {"ensaio": origem})

    # assert
    assert registros_que_referenciam(conexao, origem) == [p1, p2]
    assert registros_que_referenciam(conexao, p1) == []


def test_atualizar_trocando_a_referencia_reflete_o_ultimo_salvamento(conexao):
    # arrange
    _, v_ensaio = _formulario(conexao, "ensaio")
    _, v_proctor = _formulario(conexao, "proctor")
    e1, e2 = _registro(conexao, v_ensaio), _registro(conexao, v_ensaio)
    proctor = _registro(conexao, v_proctor)
    substituir_referencias(conexao, proctor, {"ensaio": e1})

    # act
    substituir_referencias(conexao, proctor, {"ensaio": e2})

    # assert
    assert registros_que_referenciam(conexao, e1) == []
    assert registros_que_referenciam(conexao, e2) == [proctor]
    assert obter_referencias(conexao, proctor) == {"ensaio": e2}


def test_remover_a_referencia_apaga_o_vinculo(conexao):
    # arrange
    _, v_ensaio = _formulario(conexao, "ensaio")
    _, v_proctor = _formulario(conexao, "proctor")
    origem, proctor = _registro(conexao, v_ensaio), _registro(conexao, v_proctor)
    substituir_referencias(conexao, proctor, {"ensaio": origem})

    # act
    substituir_referencias(conexao, proctor, {})

    # assert
    assert registros_que_referenciam(conexao, origem) == []


def test_varias_referencias_no_mesmo_registro(conexao):
    # arrange
    _, v_a = _formulario(conexao, "a")
    _, v_b = _formulario(conexao, "b")
    _, v_c = _formulario(conexao, "c")
    ra, rb, rc = _registro(conexao, v_a), _registro(conexao, v_b), _registro(conexao, v_c)

    # act
    substituir_referencias(conexao, rc, {"origem_a": ra, "origem_b": rb})

    # assert
    assert obter_referencias(conexao, rc) == {"origem_a": ra, "origem_b": rb}
    assert registros_que_referenciam(conexao, ra) == [rc]


def test_referencia_para_registro_inexistente_e_recusada_pelo_banco(conexao):
    # arrange
    _, versao = _formulario(conexao, "proctor")
    proctor = _registro(conexao, versao)

    # act / assert
    with pytest.raises(psycopg.errors.IntegrityError):
        substituir_referencias(conexao, proctor, {"ensaio": 999})


# --- dependentes transitivos de um registro (cascata) ---


def test_registros_dependentes_transitivos_vem_em_ordem_de_dependencia(conexao):
    # arrange: insitu -> proctor -> ensaio (cada um é um registro)
    _, v_ensaio = _formulario(conexao, "ensaio")
    _, v_proctor = _formulario(conexao, "proctor")
    _, v_insitu = _formulario(conexao, "insitu")
    ensaio = _registro(conexao, v_ensaio)
    proctor = _registro(conexao, v_proctor)
    insitu = _registro(conexao, v_insitu)
    substituir_referencias(conexao, proctor, {"ensaio": ensaio})
    substituir_referencias(conexao, insitu, {"proctor": proctor})

    # act / assert: o proctor vem antes do insitu, que depende dele
    assert registros_dependentes(conexao, ensaio) == [proctor, insitu]
    assert registros_dependentes(conexao, proctor) == [insitu]
    assert registros_dependentes(conexao, insitu) == []


def test_diamante_de_registros_calcula_o_no_comum_depois_dos_dois_caminhos(conexao):
    # arrange: d referencia b e c; b e c referenciam a; e b referencia c também (caminho mais longo)
    _, va = _formulario(conexao, "a")
    _, vb = _formulario(conexao, "b")
    _, vc = _formulario(conexao, "c")
    _, vd = _formulario(conexao, "d")
    a, b, c, d = (_registro(conexao, v) for v in (va, vb, vc, vd))
    substituir_referencias(conexao, c, {"a": a})
    substituir_referencias(conexao, b, {"a": a, "c": c})
    substituir_referencias(conexao, d, {"b": b, "c": c})

    # act
    ordem = registros_dependentes(conexao, a)

    # assert: c antes de b (b depende de c), e d por último
    assert ordem == [c, b, d]


def test_sem_dependentes_devolve_lista_vazia(conexao):
    # arrange
    _, versao = _formulario(conexao, "ensaio")

    # act / assert
    assert registros_dependentes(conexao, _registro(conexao, versao)) == []
