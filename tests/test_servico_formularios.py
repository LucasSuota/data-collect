import sqlite3
from datetime import UTC, datetime

import pytest

from forms import servico
from forms.models import DefinicaoInvalida, LoteInvalido, NaoEncontrado
from forms.repositorio import abrir_conexao, listar_dependencias
from forms.servico import Rascunho

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEPOIS = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)

ENSAIO = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "compartilhado": True},
        {"id": "data", "tipo": "data", "rotulo": "Data", "compartilhado": True},
        {"id": "operador", "tipo": "texto", "rotulo": "Operador", "compartilhado": True},
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
        {"id": "massa", "tipo": "numero", "rotulo": "Massa", "compartilhado": True},
        {
            "id": "seca",
            "tipo": "calculado",
            "rotulo": "Massa seca",
            "formula": "massa * (1 - ensaio__umidade)",
            "compartilhado": True,
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


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


def _criar(conexao, nome, definicao, quando=AGORA):
    return servico.criar_formulario(conexao, nome, definicao, quando)


def _contagens(conexao: sqlite3.Connection) -> tuple[int, int, int]:
    def contar(tabela: str) -> int:
        # nome de tabela de constante do teste, nunca de entrada externa
        return conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]

    return contar("formularios"), contar("versoes_formulario"), contar("dependencias_formulario")


def _erros(excecao: pytest.ExceptionInfo[DefinicaoInvalida]) -> dict[str, str]:
    return {erro.campo: erro.mensagem for erro in excecao.value.erros}


# --- criar formulário (#21) ---


def test_criar_formulario_cria_o_formulario_e_a_versao_1(conexao):
    # act
    criado = _criar(conexao, "ensaio", ENSAIO)

    # assert
    assert criado.formulario.nome == "ensaio"
    assert criado.versao.numero == 1
    assert criado.versao.formulario_id == criado.formulario.id
    assert [c.id for c in criado.versao.definicao.campos] == ["umidade", "data", "operador", "obs"]


def test_definicao_invalida_nao_cria_nada(conexao):
    # arrange
    invalida = {"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "ensaio", invalida)

    # assert
    assert "a.tipo" in _erros(excecao)
    assert _contagens(conexao) == (0, 0, 0)


def test_definicao_invalida_devolve_todos_os_erros(conexao):
    # arrange
    invalida = {
        "campos": [
            {"id": "pi", "tipo": "texto", "rotulo": "A"},
            {"id": "b", "tipo": "telefone", "rotulo": "B"},
        ]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "ensaio", invalida)

    # assert
    assert set(_erros(excecao)) == {"campos[0].id", "b.tipo"}


@pytest.mark.parametrize("repetido", ["ensaio", "ENSAIO", "  Ensaio  "])
def test_nome_repetido_gera_erro_no_campo_nome_e_nao_cria_nada(conexao, repetido):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, repetido, ENSAIO)

    # assert
    assert list(_erros(excecao)) == ["nome"]
    assert _contagens(conexao) == (1, 1, 0)


def test_nome_vazio_gera_erro_no_campo_nome(conexao):
    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "   ", ENSAIO)

    # assert
    assert list(_erros(excecao)) == ["nome"]


def test_nome_e_definicao_invalidos_juntos_reportam_os_dois(conexao):
    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "", {"campos": [{"id": "a", "tipo": "x", "rotulo": "A"}]})

    # assert
    assert set(_erros(excecao)) == {"nome", "a.tipo"}


def test_banco_fica_como_estava_se_a_gravacao_falhar_no_meio(conexao, monkeypatch):
    # arrange: a publicação da versão explode depois de o formulário já ter sido inserido
    def explodir(*argumentos, **nomeados):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(servico.repositorio, "inserir_versao", explodir)

    # act
    with pytest.raises(RuntimeError):
        _criar(conexao, "ensaio", ENSAIO)

    # assert: nem o formulário ficou
    assert _contagens(conexao) == (0, 0, 0)
    assert not conexao.in_transaction


# --- publicar versão (#21) ---


def test_segunda_versao_tem_numero_2_e_a_primeira_nao_muda(conexao):
    # arrange
    criado = _criar(conexao, "ensaio", ENSAIO)
    nova = {"campos": ENSAIO["campos"] + [{"id": "extra", "tipo": "texto", "rotulo": "Extra"}]}

    # act
    segunda = servico.publicar_versao(conexao, criado.formulario.id, nova, DEPOIS)

    # assert
    assert segunda.numero == 2
    primeira = servico.obter_versao(conexao, criado.formulario.id, criado.versao.id)
    assert len(primeira.definicao.campos) == 4 and len(segunda.definicao.campos) == 5


def test_numeracao_e_sequencial_por_formulario(conexao):
    # arrange
    a = _criar(conexao, "a", ENSAIO)
    b = _criar(conexao, "b", ENSAIO)

    # act
    servico.publicar_versao(conexao, a.formulario.id, ENSAIO, DEPOIS)
    terceira = servico.publicar_versao(conexao, a.formulario.id, ENSAIO, DEPOIS)
    segunda_de_b = servico.publicar_versao(conexao, b.formulario.id, ENSAIO, DEPOIS)

    # assert
    assert (terceira.numero, segunda_de_b.numero) == (3, 2)


def test_versao_invalida_nao_grava_e_a_atual_continua_a_mesma(conexao):
    # arrange
    criado = _criar(conexao, "ensaio", ENSAIO)

    # act
    with pytest.raises(DefinicaoInvalida):
        servico.publicar_versao(conexao, criado.formulario.id, {"campos": "x"}, DEPOIS)

    # assert
    assert [v.numero for v in servico.listar_versoes(conexao, criado.formulario.id)] == [1]


def test_publicar_versao_de_formulario_inexistente_e_nao_encontrado(conexao):
    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.publicar_versao(conexao, 99, ENSAIO, AGORA)


# --- leitura ---


def test_listar_formularios_traz_a_versao_atual(conexao):
    # arrange
    criado = _criar(conexao, "ensaio", ENSAIO)
    servico.publicar_versao(conexao, criado.formulario.id, ENSAIO, DEPOIS)

    # act
    (resumo,) = servico.listar_formularios(conexao)

    # assert
    assert (resumo.nome, resumo.versao_atual_numero) == ("ensaio", 2)


def test_obter_formulario_devolve_a_versao_atual_completa(conexao):
    # arrange
    criado = _criar(conexao, "ensaio", ENSAIO)
    segunda = servico.publicar_versao(conexao, criado.formulario.id, PROCTOR_SEM_REF, DEPOIS)

    # act
    detalhe = servico.obter_formulario(conexao, criado.formulario.id)

    # assert
    assert detalhe.formulario == criado.formulario
    assert detalhe.versao_atual == segunda


PROCTOR_SEM_REF = {"campos": [{"id": "massa", "tipo": "numero", "rotulo": "Massa"}]}


def test_obter_versao_de_outro_formulario_nao_e_encontrada(conexao):
    # arrange
    a = _criar(conexao, "a", ENSAIO)
    b = _criar(conexao, "b", ENSAIO)

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.obter_versao(conexao, b.formulario.id, a.versao.id)


# --- relação entre formulários ao publicar (#25) ---


def test_formulario_que_depende_de_outro_registra_a_dependencia(conexao):
    # arrange
    ensaio = _criar(conexao, "ensaio", ENSAIO)

    # act
    proctor = _criar(conexao, "proctor", PROCTOR)

    # assert
    assert listar_dependencias(conexao) == [(proctor.formulario.id, ensaio.formulario.id)]


def test_referencia_resolve_o_nome_sem_diferenciar_caixa(conexao):
    # arrange
    _criar(conexao, "Ensaio", ENSAIO)
    definicao = {
        "campos": [{"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ENSAIO"}]
    }

    # act / assert
    assert _criar(conexao, "proctor", definicao).versao.numero == 1


def test_origem_inexistente_gera_erro_localizado_no_campo_de_referencia(conexao):
    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "proctor", PROCTOR)

    # assert
    assert list(_erros(excecao)) == ["ensaio.formulario"]
    assert "não existe" in _erros(excecao)["ensaio.formulario"]
    assert _contagens(conexao) == (0, 0, 0)


def test_formula_usa_campo_compartilhado_valido_e_o_tipo_vem_da_origem(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)
    definicao = {
        "campos": [
            {"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
            {"id": "prazo", "tipo": "calculado", "rotulo": "P", "formula": "e__data + dias(3)"},
            {"id": "u", "tipo": "calculado", "rotulo": "U", "formula": "e__umidade * 2"},
        ]
    }

    # act / assert
    assert _criar(conexao, "proctor", definicao).versao.numero == 1


def test_formula_que_usa_campo_nao_compartilhado_e_rejeitada(conexao):
    # arrange: "obs" existe na origem, mas não é compartilhado
    _criar(conexao, "ensaio", ENSAIO)
    definicao = {
        "campos": [
            {"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
            {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "e__obs"},
        ]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "proctor", definicao)

    # assert
    assert list(_erros(excecao)) == ["c.formula"]
    assert "compartilha" in _erros(excecao)["c.formula"]


def test_compartilhado_de_texto_na_origem_nao_entra_em_formula(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)
    definicao = {
        "campos": [
            {"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
            {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "e__operador"},
        ]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "proctor", definicao)

    # assert
    assert "texto" in _erros(excecao)["c.formula"]


def test_cadeia_de_tres_formularios_publicados_um_a_um(conexao):
    # act
    _criar(conexao, "ensaio", ENSAIO)
    _criar(conexao, "proctor", PROCTOR)
    insitu = _criar(conexao, "insitu", INSITU)

    # assert: o tipo de "seca" (calculado) veio da origem recalculando a dela
    assert insitu.versao.numero == 1
    assert len(listar_dependencias(conexao)) == 2


def test_tipo_inferido_do_calculado_compartilhado_e_respeitado(conexao):
    # arrange: "seca" é número; usá-lo como data tem de falhar
    _criar(conexao, "ensaio", ENSAIO)
    _criar(conexao, "proctor", PROCTOR)
    definicao = {
        "campos": [
            {"id": "p", "tipo": "referencia", "rotulo": "P", "formulario": "proctor"},
            {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "p__seca + dias(1)"},
        ]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "insitu", definicao)

    # assert
    assert list(_erros(excecao)) == ["c.formula"]


def test_auto_referencia_e_rejeitada_citando_o_formulario(conexao):
    # arrange
    definicao = {
        "campos": [{"id": "eu", "tipo": "referencia", "rotulo": "Eu", "formulario": "ensaio"}]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        _criar(conexao, "ensaio", definicao)

    # assert
    assert list(_erros(excecao)) == ["eu.formulario"]
    assert "ensaio" in _erros(excecao)["eu.formulario"]
    assert _contagens(conexao) == (0, 0, 0)


def test_nova_versao_da_origem_nao_pode_passar_a_depender_de_um_dependente(conexao):
    # arrange: proctor depende de ensaio; a v2 do ensaio tentaria depender do proctor (ciclo)
    ensaio = _criar(conexao, "ensaio", ENSAIO)
    _criar(conexao, "proctor", PROCTOR)
    v2 = {
        "campos": ENSAIO["campos"]
        + [{"id": "p", "tipo": "referencia", "rotulo": "P", "formulario": "proctor"}]
    }

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, ensaio.formulario.id, v2, DEPOIS)

    # assert
    mensagem = _erros(excecao)["p.formulario"]
    assert "ensaio" in mensagem and "proctor" in mensagem
    assert [v.numero for v in servico.listar_versoes(conexao, ensaio.formulario.id)] == [1]


def test_nova_versao_do_dependente_continua_registrando_a_origem(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)
    proctor = _criar(conexao, "proctor", PROCTOR)

    # act
    servico.publicar_versao(conexao, proctor.formulario.id, PROCTOR, DEPOIS)

    # assert: sem duplicar o vínculo
    assert len(listar_dependencias(conexao)) == 1


# --- contrato dos campos compartilhados entre versões (#27) ---


def _origem_com_dependente(conexao):
    ensaio = _criar(conexao, "ensaio", ENSAIO)
    _criar(conexao, "proctor", PROCTOR)
    return ensaio.formulario.id


def _versao_de_ensaio(campos):
    return {"campos": campos}


def test_remover_campo_compartilhado_e_rejeitado_citando_campo_e_dependentes(conexao):
    # arrange
    ensaio_id = _origem_com_dependente(conexao)
    sem_umidade = _versao_de_ensaio([c for c in ENSAIO["campos"] if c["id"] != "umidade"])

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, ensaio_id, sem_umidade, DEPOIS)

    # assert
    mensagem = _erros(excecao)["umidade"]
    assert "umidade" in mensagem and "proctor" in mensagem and "remov" in mensagem


def test_deixar_de_compartilhar_e_rejeitado(conexao):
    # arrange
    ensaio_id = _origem_com_dependente(conexao)
    campos = [dict(c) for c in ENSAIO["campos"]]
    campos[0].pop("compartilhado")

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, ensaio_id, _versao_de_ensaio(campos), DEPOIS)

    # assert
    assert "proctor" in _erros(excecao)["umidade.compartilhado"]


def test_mudar_o_tipo_de_campo_compartilhado_e_rejeitado(conexao):
    # arrange
    ensaio_id = _origem_com_dependente(conexao)
    campos = [dict(c) for c in ENSAIO["campos"]]
    campos[0]["tipo"] = "data"

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, ensaio_id, _versao_de_ensaio(campos), DEPOIS)

    # assert
    mensagem = _erros(excecao)["umidade.tipo"]
    assert "numero" in mensagem and "data" in mensagem and "proctor" in mensagem


def test_mudar_o_tipo_inferido_de_calculado_compartilhado_e_rejeitado(conexao):
    # arrange: proctor.seca é número; a v2 faz "seca" virar booleano
    _criar(conexao, "ensaio", ENSAIO)
    proctor = _criar(conexao, "proctor", PROCTOR)
    _criar(conexao, "insitu", INSITU)
    campos = [dict(c) for c in PROCTOR["campos"]]
    campos[2]["formula"] = "massa > 1"

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, proctor.formulario.id, {"campos": campos}, DEPOIS)

    # assert
    mensagem = _erros(excecao)["seca.formula"]
    assert "insitu" in mensagem and "seca" in mensagem


def test_campo_novo_e_campo_nao_compartilhado_sao_livres(conexao):
    # arrange
    ensaio_id = _origem_com_dependente(conexao)
    campos = [dict(c) for c in ENSAIO["campos"] if c["id"] != "obs"]  # "obs" não era compartilhado
    campos.append({"id": "novo", "tipo": "numero", "rotulo": "Novo", "compartilhado": True})

    # act
    versao = servico.publicar_versao(conexao, ensaio_id, _versao_de_ensaio(campos), DEPOIS)

    # assert
    assert versao.numero == 2


def test_origem_sem_dependentes_pode_mudar_livremente(conexao):
    # arrange
    ensaio = _criar(conexao, "ensaio", ENSAIO)

    # act
    versao = servico.publicar_versao(
        conexao,
        ensaio.formulario.id,
        {"campos": [{"id": "x", "tipo": "texto", "rotulo": "X"}]},
        DEPOIS,
    )

    # assert
    assert versao.numero == 2


def test_varios_erros_de_contrato_vem_juntos(conexao):
    # arrange
    ensaio_id = _origem_com_dependente(conexao)
    campos = [{"id": "obs", "tipo": "texto", "rotulo": "Observação"}]

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.publicar_versao(conexao, ensaio_id, _versao_de_ensaio(campos), DEPOIS)

    # assert
    assert set(_erros(excecao)) == {"umidade", "data", "operador"}


# --- validar conjunto (#57) e lote (#58) ---


def _rascunhos(**definicoes):
    return [Rascunho(nome, definicao) for nome, definicao in definicoes.items()]


def test_cadeia_nova_em_qualquer_ordem_de_entrada_e_valida(conexao):
    # arrange
    ordens = [
        ("ensaio", "proctor", "insitu"),
        ("insitu", "proctor", "ensaio"),
        ("proctor", "insitu", "ensaio"),
    ]
    definicoes = {"ensaio": ENSAIO, "proctor": PROCTOR, "insitu": INSITU}

    # act / assert
    for ordem in ordens:
        rascunhos = [Rascunho(nome, definicoes[nome]) for nome in ordem]
        assert servico.validar_conjunto(conexao, rascunhos) == []


def test_validar_conjunto_nao_grava_nada(conexao):
    # act
    servico.validar_conjunto(conexao, _rascunhos(ensaio=ENSAIO, proctor=PROCTOR))

    # assert
    assert _contagens(conexao) == (0, 0, 0)


def test_rascunho_pode_referenciar_formulario_ja_publicado(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)

    # act / assert
    assert servico.validar_conjunto(conexao, _rascunhos(proctor=PROCTOR)) == []


def test_erros_do_conjunto_vem_agrupados_por_nome_do_formulario(conexao):
    # arrange
    ruim = {"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}

    # act
    erros = servico.validar_conjunto(conexao, _rascunhos(ensaio=ENSAIO, proctor=ruim))

    # assert
    assert [e.nome for e in erros] == ["proctor"]
    assert [x.campo for x in erros[0].erros] == ["a.tipo"]


def test_mensagens_e_posicoes_sao_as_mesmas_da_validacao_individual(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)
    definicao = {
        "campos": [
            {"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
            {
                "id": "c",
                "tipo": "calculado",
                "rotulo": "C",
                "formula": "e__umidade + __import__('os')",
            },
        ]
    }

    # act
    (do_conjunto,) = servico.validar_conjunto(conexao, _rascunhos(novo=definicao))
    with pytest.raises(DefinicaoInvalida) as individual:
        _criar(conexao, "novo", definicao)

    # assert
    assert do_conjunto.erros == individual.value.erros
    assert do_conjunto.erros[0].posicao is not None


def test_ciclo_entre_dois_rascunhos_cita_os_formularios(conexao):
    # arrange
    a = {"campos": [{"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": "b"}]}
    b = {"campos": [{"id": "s", "tipo": "referencia", "rotulo": "S", "formulario": "a"}]}

    # act
    erros = servico.validar_conjunto(conexao, _rascunhos(a=a, b=b))

    # assert
    mensagens = " ".join(e.mensagem for item in erros for e in item.erros)
    assert "a" in mensagens and "b" in mensagens and "circular" in mensagens
    assert any(x.campo.endswith(".formulario") for item in erros for x in item.erros)


def test_auto_referencia_de_rascunho_e_rejeitada(conexao):
    # arrange
    a = {"campos": [{"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": "a"}]}

    # act
    (erro,) = servico.validar_conjunto(conexao, _rascunhos(a=a))

    # assert
    assert erro.nome == "a" and "circular" in erro.erros[0].mensagem


def test_nome_repetido_dentro_do_conjunto_ou_ja_existente_e_rejeitado(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)
    rascunhos = [
        Rascunho("proctor", PROCTOR_SEM_REF),
        Rascunho("  PROCTOR ", PROCTOR_SEM_REF),
        Rascunho("Ensaio", PROCTOR_SEM_REF),
    ]

    # act
    erros = {e.nome: e.erros for e in servico.validar_conjunto(conexao, rascunhos)}

    # assert
    assert set(erros) == {"  PROCTOR ", "Ensaio"}
    assert all(e[0].campo == "nome" for e in erros.values())


def test_dependente_de_rascunho_com_erro_nao_gera_erro_em_cascata_confuso(conexao):
    # arrange
    ruim = {"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}

    # act
    erros = servico.validar_conjunto(conexao, _rascunhos(ensaio=ruim, proctor=PROCTOR))

    # assert: o proctor é avisado de que a origem precisa ser corrigida
    por_nome = {e.nome: e.erros for e in erros}
    assert "ensaio" in por_nome and "proctor" in por_nome
    assert "corrija" in por_nome["proctor"][0].mensagem.lower()


def test_lote_cria_cadeia_embaralhada_com_origem_primeiro(conexao):
    # arrange
    rascunhos = [
        Rascunho("insitu", INSITU),
        Rascunho("ensaio", ENSAIO),
        Rascunho("proctor", PROCTOR),
    ]

    # act
    criados = servico.criar_formularios_em_lote(conexao, rascunhos, AGORA)

    # assert: devolvidos na ordem de criação
    assert [c.formulario.nome for c in criados] == ["ensaio", "proctor", "insitu"]
    assert all(c.versao.numero == 1 for c in criados)
    assert _contagens(conexao) == (3, 3, 2)


def test_lote_independe_da_ordem_de_entrada(conexao):
    # arrange
    outra = abrir_conexao(":memory:")
    ordem_a = [Rascunho("ensaio", ENSAIO), Rascunho("proctor", PROCTOR), Rascunho("insitu", INSITU)]
    ordem_b = list(reversed(ordem_a))

    # act
    nomes_a = [
        c.formulario.nome for c in servico.criar_formularios_em_lote(conexao, ordem_a, AGORA)
    ]
    nomes_b = [c.formulario.nome for c in servico.criar_formularios_em_lote(outra, ordem_b, AGORA)]

    # assert
    assert nomes_a == nomes_b == ["ensaio", "proctor", "insitu"]
    outra.close()


def test_falha_no_ultimo_do_lote_nao_deixa_os_anteriores_no_banco(conexao):
    # arrange: o insitu referencia um campo que o proctor não compartilha
    insitu_ruim = {
        "campos": [
            {"id": "p", "tipo": "referencia", "rotulo": "P", "formulario": "proctor"},
            {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "p__inexistente"},
        ]
    }
    rascunhos = _rascunhos(ensaio=ENSAIO, proctor=PROCTOR, insitu=insitu_ruim)

    # act
    with pytest.raises(LoteInvalido) as excecao:
        servico.criar_formularios_em_lote(conexao, rascunhos, AGORA)

    # assert
    assert [f.nome for f in excecao.value.formularios] == ["insitu"]
    assert _contagens(conexao) == (0, 0, 0)


def test_lote_com_nome_repetido_nao_cria_nada(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)

    # act
    with pytest.raises(LoteInvalido) as excecao:
        servico.criar_formularios_em_lote(
            conexao, _rascunhos(proctor=PROCTOR_SEM_REF, ENSAIO=ENSAIO), AGORA
        )

    # assert
    assert [f.nome for f in excecao.value.formularios] == ["ENSAIO"]
    assert _contagens(conexao) == (1, 1, 0)


def test_lote_que_referencia_formulario_ja_existente(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)

    # act
    criados = servico.criar_formularios_em_lote(
        conexao, _rascunhos(insitu=INSITU, proctor=PROCTOR), AGORA
    )

    # assert
    assert [c.formulario.nome for c in criados] == ["proctor", "insitu"]
    assert _contagens(conexao) == (3, 3, 2)


def test_lote_vazio_nao_cria_nada(conexao):
    # act / assert
    assert servico.criar_formularios_em_lote(conexao, [], AGORA) == []


def test_lote_com_ciclo_nao_cria_nada(conexao):
    # arrange
    a = {"campos": [{"id": "r", "tipo": "referencia", "rotulo": "R", "formulario": "b"}]}
    b = {"campos": [{"id": "s", "tipo": "referencia", "rotulo": "S", "formulario": "a"}]}

    # act
    with pytest.raises(LoteInvalido):
        servico.criar_formularios_em_lote(conexao, _rascunhos(a=a, b=b), AGORA)

    # assert
    assert _contagens(conexao) == (0, 0, 0)


# --- validar definição e catálogo (#22, parte sem prévia) ---


def test_validar_definicao_valida_devolve_valida_e_lista_vazia(conexao):
    # act
    resultado = servico.validar_definicao(conexao, ENSAIO)

    # assert
    assert resultado.valida is True and resultado.erros == ()


def test_validar_definicao_incompleta_devolve_todos_os_erros_sem_levantar(conexao):
    # arrange
    incompleta = {"campos": [{"id": "a", "tipo": "x", "rotulo": ""}, {"tipo": "texto"}]}

    # act
    resultado = servico.validar_definicao(conexao, incompleta)

    # assert
    assert resultado.valida is False
    assert {e.campo for e in resultado.erros} >= {"a.tipo", "a.rotulo", "campos[1].id"}


def test_validar_definicao_resolve_referencias_entre_formularios_publicados(conexao):
    # arrange
    _criar(conexao, "ensaio", ENSAIO)

    # act / assert
    assert servico.validar_definicao(conexao, PROCTOR).valida is True
    assert servico.validar_definicao(conexao, INSITU).valida is False  # proctor não existe


def test_validar_definicao_nao_exige_formulario_nem_grava(conexao):
    # act
    servico.validar_definicao(conexao, ENSAIO)

    # assert
    assert _contagens(conexao) == (0, 0, 0)


def test_catalogo_sai_das_mesmas_tabelas_do_avaliador():
    # act
    catalogo = servico.catalogo()

    # assert
    assert {t.id for t in catalogo.tipos} == {
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
    assert {f.nome for f in catalogo.funcoes} == set(servico.FUNCOES)
    assert [c.nome for c in catalogo.constantes] == ["pi"]
    assert set(catalogo.nomes_reservados) == {"pi", "se", "min", "max", "media", "soma", "dias"}
    numero = next(t for t in catalogo.tipos if t.id == "numero")
    assert numero.rotulo == "Número" and "casas_decimais" in numero.propriedades
    soma = next(f for f in catalogo.funcoes if f.nome == "soma")
    assert soma.assinatura == "soma(a, b, ...)" and soma.exemplo and soma.descricao
