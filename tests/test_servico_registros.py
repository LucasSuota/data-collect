from datetime import UTC, datetime, timedelta

import pytest
from psycopg import pq

from forms.dominio.models import ExclusaoBloqueada, NaoEncontrado, RegistroInvalido
from forms.repositorios.formularios import obter_referencias
from forms.servicos import servico

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEPOIS = AGORA + timedelta(hours=3)

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
ENTRADA_VALIDA = {
    "fck_mpa": 25,
    "diametro_mm": "100",
    "data_moldagem": "2026-11-01",
    "carga_kn": 200,
}

ENSAIO = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "compartilhado": True},
        {"id": "data", "tipo": "data", "rotulo": "Data", "compartilhado": True},
        {"id": "obs", "tipo": "texto", "rotulo": "Obs"},
    ]
}
PROCTOR = {
    "campos": [
        {"id": "ensaio", "tipo": "referencia", "rotulo": "Ensaio", "formulario": "ensaio"},
        {"id": "massa", "tipo": "numero", "rotulo": "Massa"},
        {
            "id": "seca",
            "tipo": "calculado",
            "rotulo": "Massa seca",
            "formula": "massa * (1 - ensaio__umidade)",
            "compartilhado": True,
        },
        {
            "id": "prazo",
            "tipo": "calculado",
            "rotulo": "Prazo",
            "formula": "ensaio__data + dias(2)",
        },
    ]
}
INSITU = {
    "campos": [
        {"id": "proctor", "tipo": "referencia", "rotulo": "Proctor", "formulario": "proctor"},
        {
            "id": "grau",
            "tipo": "calculado",
            "rotulo": "Grau",
            "formula": "proctor__seca * 2",
        },
    ]
}


def _formulario(conexao, nome, definicao):
    return servico.criar_formulario(conexao, nome, definicao, AGORA)


def _registro(conexao, criado, dados, quando=AGORA):
    return servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, dados, quando)


def _erros(excecao: pytest.ExceptionInfo[RegistroInvalido]) -> dict[str, str]:
    return {erro.campo: erro.mensagem for erro in excecao.value.erros}


@pytest.fixture
def corpo(conexao):
    return _formulario(conexao, "corpo_de_prova", CORPO_DE_PROVA)


# --- criar (#23) ---


def test_criar_registro_valida_normaliza_calcula_e_grava(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)

    # assert
    assert registro.versao_id == corpo.versao.id and registro.formulario_id == corpo.formulario.id
    assert registro.dados["fck_mpa"] == "25"
    assert registro.dados["diametro_mm"] == "100"
    assert registro.dados["data_moldagem"] == "2026-11-01"
    assert registro.dados["ruptura_28d"] == {"valor": "2026-11-29", "erro": None}
    assert registro.dados["conforme"] == {"valor": True, "erro": None}
    assert registro.dados["resistencia_mpa"]["erro"] is None
    assert registro.dados["resistencia_mpa"]["valor"].startswith("25.4647908947")
    assert servico.obter_registro(conexao, registro.id) == registro


def test_numeros_sao_guardados_como_string_com_as_casas_digitadas(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, ENTRADA_VALIDA | {"fck_mpa": 25.5, "carga_kn": "200.50"})

    # assert
    assert registro.dados["fck_mpa"] == "25.5" and registro.dados["carga_kn"] == "200.50"


def test_campos_de_entrada_vazios_sao_guardados_como_nulos(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, {"fck_mpa": 25})

    # assert
    assert registro.dados["diametro_mm"] is None and registro.dados["data_moldagem"] is None


def test_entrada_vazia_gera_calculado_com_valor_e_erro_nulos(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, {"fck_mpa": 25})

    # assert
    assert registro.dados["resistencia_mpa"] == {"valor": None, "erro": None}
    assert registro.dados["conforme"] == {"valor": None, "erro": None}


def test_divisao_por_zero_salva_o_registro_com_erro_no_campo(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, ENTRADA_VALIDA | {"diametro_mm": 0})

    # assert: o registro foi salvo, o erro está no campo e os outros calculados seguem
    assert servico.obter_registro(conexao, registro.id) == registro
    assert registro.dados["resistencia_mpa"]["valor"] is None
    assert "zero" in registro.dados["resistencia_mpa"]["erro"].lower()
    assert "resistencia_mpa" in registro.dados["conforme"]["erro"]
    assert registro.dados["ruptura_28d"] == {"valor": "2026-11-29", "erro": None}


def test_cliente_nunca_define_valor_de_campo_calculado(conexao, corpo):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, corpo, ENTRADA_VALIDA | {"conforme": True})

    # assert
    assert list(_erros(excecao)) == ["conforme"]
    assert "calculado" in _erros(excecao)["conforme"]


def test_chave_inexistente_e_erro_no_campo(conexao, corpo):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, corpo, ENTRADA_VALIDA | {"fantasma": 1})

    # assert
    assert list(_erros(excecao)) == ["fantasma"]


def test_erros_de_validacao_vem_todos_por_id_e_nada_e_salvo(conexao, corpo):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, corpo, {"diametro_mm": "abc", "data_moldagem": "01/11/2026", "x": 1})

    # assert
    assert set(_erros(excecao)) == {"fck_mpa", "diametro_mm", "data_moldagem", "x"}
    assert servico.listar_registros(conexao, corpo.formulario.id).total == 0


def test_versao_inexistente_ou_de_outro_formulario_e_nao_encontrada(conexao, corpo):
    # arrange
    outro = _formulario(conexao, "outro", ENSAIO)

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.criar_registro(conexao, corpo.formulario.id, 999, ENTRADA_VALIDA, AGORA)
    with pytest.raises(NaoEncontrado):
        servico.criar_registro(conexao, corpo.formulario.id, outro.versao.id, ENTRADA_VALIDA, AGORA)


def test_dados_que_nao_sao_objeto_geram_erro(conexao, corpo):
    # act
    with pytest.raises(RegistroInvalido):
        servico.criar_registro(conexao, corpo.formulario.id, corpo.versao.id, [1, 2], AGORA)


# --- atualizar (#23) ---


def test_atualizar_substitui_os_valores_recalcula_e_mantem_a_versao(conexao, corpo):
    # arrange
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)

    # act: sem diâmetro nem carga; não é um PATCH, tudo é substituído
    novo = servico.atualizar_registro(
        conexao, registro.id, {"fck_mpa": 30, "data_moldagem": "2026-12-01"}, DEPOIS
    )

    # assert
    assert novo.versao_id == registro.versao_id
    assert novo.criado_em == registro.criado_em and novo.atualizado_em != registro.atualizado_em
    assert novo.dados["fck_mpa"] == "30" and novo.dados["diametro_mm"] is None
    assert novo.dados["ruptura_28d"] == {"valor": "2026-12-29", "erro": None}
    assert novo.dados["resistencia_mpa"] == {"valor": None, "erro": None}


def test_atualizar_com_erro_de_validacao_nao_altera_o_registro(conexao, corpo):
    # arrange
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)

    # act
    with pytest.raises(RegistroInvalido):
        servico.atualizar_registro(conexao, registro.id, {"fck_mpa": "abc"}, DEPOIS)

    # assert
    assert servico.obter_registro(conexao, registro.id) == registro


def test_atualizar_registro_inexistente_e_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.atualizar_registro(conexao, 99, {}, AGORA)


def test_registro_antigo_continua_valido_depois_de_publicar_a_v2(conexao, corpo):
    # arrange: a v2 acrescenta um campo obrigatório que o registro da v1 não tem
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)
    v2 = {
        "campos": CORPO_DE_PROVA["campos"]
        + [{"id": "lote", "tipo": "texto", "rotulo": "Lote", "obrigatorio": True}]
    }
    servico.publicar_versao(conexao, corpo.formulario.id, v2, DEPOIS)

    # act: editar o registro antigo valida contra a versão dele, não contra a v2
    novo = servico.atualizar_registro(
        conexao, registro.id, ENTRADA_VALIDA | {"fck_mpa": 40}, DEPOIS
    )

    # assert
    assert novo.versao_id == corpo.versao.id and "lote" not in novo.dados


def test_criar_na_versao_antiga_depois_da_v2_e_permitido_porque_a_versao_e_explicita(
    conexao, corpo
):
    # arrange
    v2 = {"campos": CORPO_DE_PROVA["campos"][:1]}
    servico.publicar_versao(conexao, corpo.formulario.id, v2, DEPOIS)

    # act
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)

    # assert
    assert registro.versao_id == corpo.versao.id


# --- excluir ---


def test_excluir_registro_livre_apaga_de_verdade(conexao, corpo):
    # arrange
    registro = _registro(conexao, corpo, ENTRADA_VALIDA)

    # act
    servico.excluir_registro(conexao, registro.id, AGORA)

    # assert
    with pytest.raises(NaoEncontrado):
        servico.obter_registro(conexao, registro.id)


def test_excluir_registro_inexistente_e_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.excluir_registro(conexao, 99, AGORA)


# --- referência e campos compartilhados (#26) ---


@pytest.fixture
def cadeia(conexao):
    return (
        _formulario(conexao, "ensaio", ENSAIO),
        _formulario(conexao, "proctor", PROCTOR),
        _formulario(conexao, "insitu", INSITU),
    )


def _ensaio(conexao, cadeia, umidade="0.1", data="2026-01-01"):
    return _registro(conexao, cadeia[0], {"umidade": umidade, "data": data})


def _proctor(conexao, cadeia, ensaio_id, massa="100", quando=AGORA):
    return _registro(conexao, cadeia[1], {"ensaio": ensaio_id, "massa": massa}, quando)


def test_calculado_usa_os_campos_compartilhados_da_origem(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia, umidade="0.1", data="2026-01-01")

    # act
    proctor = _proctor(conexao, cadeia, ensaio.id, massa="100")

    # assert
    assert proctor.dados["ensaio"] == ensaio.id
    assert proctor.dados["seca"] == {"valor": "90.0", "erro": None}
    assert proctor.dados["prazo"] == {"valor": "2026-01-03", "erro": None}


def test_referencia_inexistente_e_erro_no_campo(conexao, cadeia):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _proctor(conexao, cadeia, 999)

    # assert
    assert list(_erros(excecao)) == ["ensaio"]
    assert "999" in _erros(excecao)["ensaio"]


def test_referencia_para_registro_de_outro_formulario_e_erro(conexao, cadeia):
    # arrange: o registro 1 é de um insitu, não de um ensaio
    ensaio = _ensaio(conexao, cadeia)
    proctor = _proctor(conexao, cadeia, ensaio.id)

    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _proctor(conexao, cadeia, proctor.id)

    # assert
    assert "ensaio" in _erros(excecao)["ensaio"]


def test_referencia_vazia_deixa_os_compartilhados_vazios(conexao, cadeia):
    # act
    proctor = _registro(conexao, cadeia[1], {"massa": "100"})

    # assert
    assert proctor.dados["ensaio"] is None
    assert proctor.dados["seca"] == {"valor": None, "erro": None}
    assert proctor.dados["prazo"] == {"valor": None, "erro": None}


def test_referencia_obrigatoria_vazia_e_erro(conexao):
    # arrange
    _formulario(conexao, "ensaio", ENSAIO)
    obrigatorio = {"campos": [dict(PROCTOR["campos"][0], obrigatorio=True)]}
    proctor = _formulario(conexao, "proctor", obrigatorio)

    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, proctor, {})

    # assert
    assert _erros(excecao) == {"ensaio": "Campo obrigatório."}


def test_varios_dependentes_podem_apontar_para_a_mesma_origem(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia)

    # act
    p1, p2 = (
        _proctor(conexao, cadeia, ensaio.id, "100"),
        _proctor(conexao, cadeia, ensaio.id, "200"),
    )

    # assert
    assert p1.dados["seca"]["valor"] == "90.0" and p2.dados["seca"]["valor"] == "180.0"
    assert (
        obter_referencias(conexao, p1.id)
        == obter_referencias(conexao, p2.id)
        == {"ensaio": ensaio.id}
    )


def test_referencias_ficam_refletidas_depois_de_trocar_a_origem(conexao, cadeia):
    # arrange
    e1, e2 = _ensaio(conexao, cadeia), _ensaio(conexao, cadeia, umidade="0.5")
    proctor = _proctor(conexao, cadeia, e1.id)

    # act
    novo = servico.atualizar_registro(
        conexao, proctor.id, {"ensaio": e2.id, "massa": "100"}, DEPOIS
    )

    # assert
    assert obter_referencias(conexao, proctor.id) == {"ensaio": e2.id}
    assert novo.dados["seca"]["valor"] == "50.0"


def test_origem_em_versao_antiga_sem_o_campo_conta_como_vazio(conexao, cadeia):
    # arrange: o ensaio v1 não tem "turno"; a v2 passa a compartilhá-lo e o proctor v2 o usa
    ensaio = _ensaio(conexao, cadeia)
    ensaio_v2 = {
        "campos": ENSAIO["campos"]
        + [{"id": "turno", "tipo": "numero", "rotulo": "Turno", "compartilhado": True}]
    }
    servico.publicar_versao(conexao, cadeia[0].formulario.id, ensaio_v2, DEPOIS)
    proctor_v2 = {
        "campos": PROCTOR["campos"]
        + [
            {
                "id": "total",
                "tipo": "calculado",
                "rotulo": "Total",
                "formula": "massa + ensaio__turno",
            }
        ]
    }
    versao = servico.publicar_versao(conexao, cadeia[1].formulario.id, proctor_v2, DEPOIS)

    # act: o registro de origem é da v1 (sem o campo "turno")
    proctor = servico.criar_registro(
        conexao, cadeia[1].formulario.id, versao.id, {"ensaio": ensaio.id, "massa": "5"}, DEPOIS
    )

    # assert
    assert proctor.dados["total"] == {"valor": None, "erro": None}
    assert proctor.dados["seca"]["erro"] is None


def test_erro_de_calculo_na_origem_propaga_citando_o_campo_de_origem(conexao):
    # arrange: a origem compartilha um calculado que divide por zero
    origem = {
        "campos": [
            {"id": "x", "tipo": "numero", "rotulo": "X"},
            {
                "id": "inverso",
                "tipo": "calculado",
                "rotulo": "Inverso",
                "formula": "1 / x",
                "compartilhado": True,
            },
        ]
    }
    dependente = {
        "campos": [
            {"id": "o", "tipo": "referencia", "rotulo": "O", "formulario": "origem"},
            {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "o__inverso * 2"},
        ]
    }
    origem_f = _formulario(conexao, "origem", origem)
    dependente_f = _formulario(conexao, "dependente", dependente)
    registro_origem = _registro(conexao, origem_f, {"x": 0})

    # act
    registro = _registro(conexao, dependente_f, {"o": registro_origem.id})

    # assert
    assert registro.dados["dobro"]["valor"] is None
    assert (
        "o__inverso" in registro.dados["dobro"]["erro"]
        and "zero" in registro.dados["dobro"]["erro"].lower()
    )


# --- cascata (#28) ---


def test_atualizar_a_origem_recalcula_os_dependentes_transitivos_na_mesma_transacao(
    conexao, cadeia
):
    # arrange: ensaio -> proctor -> insitu
    ensaio = _ensaio(conexao, cadeia, umidade="0.1")
    proctor = _proctor(conexao, cadeia, ensaio.id, massa="100")
    insitu = _registro(conexao, cadeia[2], {"proctor": proctor.id})
    assert insitu.dados["grau"]["valor"] == "180.0"

    # act
    servico.atualizar_registro(conexao, ensaio.id, {"umidade": "0.5", "data": "2026-03-01"}, DEPOIS)

    # assert
    proctor_depois = servico.obter_registro(conexao, proctor.id)
    insitu_depois = servico.obter_registro(conexao, insitu.id)
    assert proctor_depois.dados["seca"]["valor"] == "50.0"
    assert proctor_depois.dados["prazo"]["valor"] == "2026-03-03"
    assert insitu_depois.dados["grau"]["valor"] == "100.0"
    assert proctor_depois.dados["massa"] == "100"  # os campos de entrada do dependente não mudam


def test_cascata_mantem_a_versao_de_cada_dependente(conexao, cadeia):
    # arrange: o proctor nasceu na v1; depois sai a v2 do proctor
    ensaio = _ensaio(conexao, cadeia)
    proctor = _proctor(conexao, cadeia, ensaio.id)
    servico.publicar_versao(conexao, cadeia[1].formulario.id, PROCTOR, DEPOIS)

    # act
    servico.atualizar_registro(conexao, ensaio.id, {"umidade": "0.2", "data": "2026-01-01"}, DEPOIS)

    # assert
    assert servico.obter_registro(conexao, proctor.id).versao_id == cadeia[1].versao.id


def test_cascata_atualiza_a_data_de_modificacao_so_de_quem_mudou(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia)
    mudou = _proctor(conexao, cadeia, ensaio.id)
    quieto = _registro(conexao, cadeia[1], {"massa": "1"})  # sem referência: não depende do ensaio

    # act
    servico.atualizar_registro(conexao, ensaio.id, {"umidade": "0.9", "data": "2026-01-01"}, DEPOIS)

    # assert
    assert servico.obter_registro(conexao, mudou.id).atualizado_em == DEPOIS.isoformat(
        timespec="seconds"
    )
    assert servico.obter_registro(conexao, quieto.id).atualizado_em == quieto.atualizado_em


def test_atualizar_sem_mudar_o_que_o_dependente_usa_nao_regrava_o_dependente(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia)
    proctor = _proctor(conexao, cadeia, ensaio.id)

    # act: só o campo não compartilhado muda
    servico.atualizar_registro(
        conexao, ensaio.id, {"umidade": "0.1", "data": "2026-01-01", "obs": "novo"}, DEPOIS
    )

    # assert
    assert servico.obter_registro(conexao, proctor.id).atualizado_em == proctor.atualizado_em


def test_erro_de_calculo_no_dependente_vira_erro_no_campo_e_nao_reverte_a_origem(conexao):
    # arrange
    origem = {"campos": [{"id": "v", "tipo": "numero", "rotulo": "V", "compartilhado": True}]}
    dependente = {
        "campos": [
            {"id": "o", "tipo": "referencia", "rotulo": "O", "formulario": "origem"},
            {"id": "inverso", "tipo": "calculado", "rotulo": "Inverso", "formula": "1 / o__v"},
        ]
    }
    origem_f = _formulario(conexao, "origem", origem)
    dependente_f = _formulario(conexao, "dependente", dependente)
    reg_origem = _registro(conexao, origem_f, {"v": 2})
    reg_dependente = _registro(conexao, dependente_f, {"o": reg_origem.id})
    assert reg_dependente.dados["inverso"]["valor"] == "0.5"

    # act: a edição da origem faz o dependente dividir por zero
    servico.atualizar_registro(conexao, reg_origem.id, {"v": 0}, DEPOIS)

    # assert
    assert servico.obter_registro(conexao, reg_origem.id).dados["v"] == "0"
    erro = servico.obter_registro(conexao, reg_dependente.id).dados["inverso"]
    assert erro["valor"] is None and "zero" in erro["erro"].lower()


def test_criar_registro_nao_dispara_cascata(conexao, cadeia):
    # act / assert: criar não tem dependentes; só confirma que nada quebra e nada extra é gravado
    ensaio = _ensaio(conexao, cadeia)
    assert servico.listar_registros(conexao, cadeia[1].formulario.id).total == 0
    assert ensaio.dados["umidade"] == "0.1"


def test_falha_no_meio_da_cascata_desfaz_tambem_a_edicao_da_origem(conexao, cadeia, monkeypatch):
    # arrange
    ensaio = _ensaio(conexao, cadeia, umidade="0.1")
    _proctor(conexao, cadeia, ensaio.id)
    original = servico.repositorio.atualizar_registro
    chamadas = []

    def falha_no_segundo(conexao_, registro_id, dados, agora, **nomeados):
        chamadas.append(registro_id)
        if len(chamadas) == 2:  # o primeiro é a origem; o segundo é o dependente
            raise RuntimeError("falha simulada na cascata")
        return original(conexao_, registro_id, dados, agora, **nomeados)

    monkeypatch.setattr(servico.repositorio, "atualizar_registro", falha_no_segundo)

    # act
    with pytest.raises(RuntimeError):
        servico.atualizar_registro(
            conexao, ensaio.id, {"umidade": "0.9", "data": "2026-01-01"}, DEPOIS
        )

    # assert: a origem voltou ao que era
    assert servico.obter_registro(conexao, ensaio.id).dados["umidade"] == "0.1"
    assert conexao.info.transaction_status == pq.TransactionStatus.IDLE


# --- exclusão com bloqueio (#29) ---


def test_registro_referenciado_nao_pode_ser_excluido(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia)
    proctor = _proctor(conexao, cadeia, ensaio.id)

    # act
    with pytest.raises(ExclusaoBloqueada) as excecao:
        servico.excluir_registro(conexao, ensaio.id, AGORA)

    # assert
    assert str(proctor.id) in str(excecao.value)
    assert servico.obter_registro(conexao, ensaio.id) == ensaio


def test_registro_pode_ser_excluido_quando_o_dependente_some(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia)
    proctor = _proctor(conexao, cadeia, ensaio.id)

    # act
    servico.excluir_registro(conexao, proctor.id, AGORA)
    servico.excluir_registro(conexao, ensaio.id, AGORA)

    # assert
    with pytest.raises(NaoEncontrado):
        servico.obter_registro(conexao, ensaio.id)


def test_formulario_com_dependente_nao_pode_ser_excluido(conexao, cadeia):
    # act
    with pytest.raises(ExclusaoBloqueada) as excecao:
        servico.excluir_formulario(conexao, cadeia[0].formulario.id)

    # assert
    assert "proctor" in str(excecao.value)


def test_formulario_com_registros_nao_pode_ser_excluido(conexao, corpo):
    # arrange
    _registro(conexao, corpo, ENTRADA_VALIDA)

    # act
    with pytest.raises(ExclusaoBloqueada) as excecao:
        servico.excluir_formulario(conexao, corpo.formulario.id)

    # assert
    assert "registro" in str(excecao.value)


def test_formulario_livre_e_excluido_com_suas_versoes(conexao, corpo):
    # arrange
    servico.publicar_versao(conexao, corpo.formulario.id, CORPO_DE_PROVA, DEPOIS)

    # act
    servico.excluir_formulario(conexao, corpo.formulario.id)

    # assert
    with pytest.raises(NaoEncontrado):
        servico.obter_formulario(conexao, corpo.formulario.id)
    assert conexao.execute("SELECT COUNT(*) FROM versoes_formulario").fetchone()[0] == 0


def test_excluir_formulario_inexistente_e_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.excluir_formulario(conexao, 99)


def test_formulario_dependente_pode_ser_excluido_e_libera_a_origem(conexao, cadeia):
    # act: o insitu e depois o proctor não têm registros nem dependentes
    servico.excluir_formulario(conexao, cadeia[2].formulario.id)
    servico.excluir_formulario(conexao, cadeia[1].formulario.id)
    servico.excluir_formulario(conexao, cadeia[0].formulario.id)

    # assert
    assert servico.listar_formularios(conexao) == []


# --- prévia (#22) ---


def test_previa_calcula_sem_gravar_nada(conexao, corpo):
    # act
    resultado = servico.previa(conexao, CORPO_DE_PROVA, ENTRADA_VALIDA)

    # assert
    assert resultado.valida is True and resultado.erros == ()
    assert resultado.calculados["conforme"].valor is True
    assert resultado.calculados["ruptura_28d"].valor == "2026-11-29"
    assert servico.listar_registros(conexao, corpo.formulario.id).total == 0


def test_previa_e_salvar_produzem_o_mesmo_calculo_para_a_mesma_entrada(conexao, corpo):
    # act
    previa = servico.previa(conexao, CORPO_DE_PROVA, ENTRADA_VALIDA)
    salvo = _registro(conexao, corpo, ENTRADA_VALIDA)

    # assert
    for id_do_campo, resultado in previa.calculados.items():
        assert salvo.dados[id_do_campo] == {"valor": resultado.valor, "erro": resultado.erro}


def test_previa_com_entrada_vazia_e_com_erro_de_calculo(conexao):
    # act
    vazia = servico.previa(conexao, CORPO_DE_PROVA, {})
    com_erro = servico.previa(conexao, CORPO_DE_PROVA, ENTRADA_VALIDA | {"diametro_mm": 0})

    # assert
    assert (
        vazia.calculados["resistencia_mpa"].valor is None
        and vazia.calculados["resistencia_mpa"].erro is None
    )
    assert "zero" in com_erro.calculados["resistencia_mpa"].erro.lower()


def test_previa_nao_exige_campos_obrigatorios_nem_valores_completos(conexao):
    # act: enquanto digita, fck ainda não foi informado e o diâmetro está pela metade
    resultado = servico.previa(conexao, CORPO_DE_PROVA, {"diametro_mm": "10,", "carga_kn": 5})

    # assert
    assert resultado.valida is True
    assert resultado.calculados["resistencia_mpa"].valor is None


def test_previa_de_definicao_invalida_devolve_a_mesma_lista_de_erros_do_validar(conexao):
    # arrange
    invalida = {"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}

    # act
    previa = servico.previa(conexao, invalida, {})
    validar = servico.validar_definicao(conexao, invalida)

    # assert
    assert previa.valida is False and previa.erros == validar.erros and previa.calculados == {}


def test_previa_usa_o_registro_de_origem_informado_na_referencia(conexao, cadeia):
    # arrange
    ensaio = _ensaio(conexao, cadeia, umidade="0.2")

    # act
    com_origem = servico.previa(conexao, PROCTOR, {"ensaio": ensaio.id, "massa": "100"})
    sem_origem = servico.previa(conexao, PROCTOR, {"massa": "100"})
    origem_inexistente = servico.previa(conexao, PROCTOR, {"ensaio": 999, "massa": "100"})

    # assert
    assert com_origem.calculados["seca"].valor == "80.0"
    assert sem_origem.calculados["seca"].valor is None
    assert origem_inexistente.calculados["seca"].valor is None
