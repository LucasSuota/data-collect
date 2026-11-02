from datetime import UTC, date, datetime, timedelta

import pytest

from forms import servico
from forms.models import NaoEncontrado, RegistroInvalido, TipoCampo
from forms.repositorio import abrir_conexao

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)

DEFINICAO = {
    "campos": [
        {"id": "secao_a", "tipo": "secao", "rotulo": "Dados"},
        {"id": "resultado", "tipo": "selecao", "rotulo": "Resultado", "opcoes": ["OK", "Falha"]},
        {"id": "ensaiado", "tipo": "sim_nao", "rotulo": "Ensaiado?"},
        {"id": "obs", "tipo": "texto", "rotulo": "Observação"},
        {"id": "carga", "tipo": "numero", "rotulo": "Carga", "unidade": "kN", "casas_decimais": 1},
        {"id": "dia", "tipo": "data", "rotulo": "Dia"},
        {
            "id": "dobro",
            "tipo": "calculado",
            "rotulo": "Dobro",
            "formula": "carga * 2",
            "casas_decimais": 1,
        },
        {"id": "alto", "tipo": "calculado", "rotulo": "Alto?", "formula": "carga > 10"},
        {"id": "local", "tipo": "localizacao", "rotulo": "Local"},
    ]
}


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def criado(conexao):
    return servico.criar_formulario(conexao, "ensaio", DEFINICAO, AGORA)


def _novo(conexao, criado, dados, quando=AGORA):
    return servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, dados, quando)


@pytest.fixture
def carregado(conexao, criado):
    _novo(
        conexao,
        criado,
        {"resultado": "OK", "ensaiado": True, "obs": "alfa", "carga": "12.34", "dia": "2026-11-01"},
    )
    _novo(conexao, criado, {"resultado": "Falha", "ensaiado": False, "obs": "beta", "carga": "5"})
    _novo(
        conexao,
        criado,
        {"resultado": "OK", "ensaiado": True, "obs": "=cmd|' /C calc'!A0", "carga": "-3.5"},
    )
    return criado


# --- colunas ---


def test_colunas_vem_da_definicao_sem_secao_e_na_ordem(conexao, carregado):
    # act
    listagem = servico.listar_registros(conexao, carregado.formulario.id)

    # assert
    assert [c.id for c in listagem.colunas] == [
        "resultado",
        "ensaiado",
        "obs",
        "carga",
        "dia",
        "dobro",
        "alto",
        "local",
    ]
    carga = next(c for c in listagem.colunas if c.id == "carga")
    assert (carga.rotulo, carga.unidade, carga.casas_decimais) == ("Carga", "kN", 1)
    assert next(c for c in listagem.colunas if c.id == "alto").tipo is TipoCampo.CALCULADO


def test_listagem_traz_total_e_itens_do_mais_recente_ao_mais_antigo(conexao, carregado):
    # act
    listagem = servico.listar_registros(conexao, carregado.formulario.id)

    # assert
    assert listagem.total == 3 and len(listagem.itens) == 3
    assert [r.id for r in listagem.itens] == sorted((r.id for r in listagem.itens), reverse=True)
    assert listagem.versao_id == carregado.versao.id


# --- versão ---


def test_padrao_e_a_ultima_versao_e_versao_antiga_continua_acessivel(conexao, carregado):
    # arrange
    v2 = servico.publicar_versao(
        conexao,
        carregado.formulario.id,
        {"campos": [{"id": "x", "tipo": "texto", "rotulo": "X"}]},
        AGORA,
    )
    servico.criar_registro(conexao, carregado.formulario.id, v2.id, {"x": "novo"}, AGORA)

    # act
    ultima = servico.listar_registros(conexao, carregado.formulario.id)
    antiga = servico.listar_registros(
        conexao, carregado.formulario.id, versao_id=carregado.versao.id
    )

    # assert
    assert (
        ultima.versao_id == v2.id and ultima.total == 1 and [c.id for c in ultima.colunas] == ["x"]
    )
    assert antiga.versao_id == carregado.versao.id and antiga.total == 3
    assert "carga" in [c.id for c in antiga.colunas]


def test_versao_de_outro_formulario_nao_e_encontrada(conexao, carregado):
    # arrange
    outro = servico.criar_formulario(conexao, "outro", {"campos": []}, AGORA)

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.listar_registros(conexao, carregado.formulario.id, versao_id=outro.versao.id)


# --- paginação ---


def test_paginacao_com_limite_e_deslocamento(conexao, carregado):
    # act
    primeira = servico.listar_registros(conexao, carregado.formulario.id, limite=2)
    segunda = servico.listar_registros(conexao, carregado.formulario.id, limite=2, deslocamento=2)

    # assert
    assert (len(primeira.itens), len(segunda.itens), primeira.total) == (2, 1, 3)


@pytest.mark.parametrize(
    ("limite", "deslocamento", "campo"),
    [(0, 0, "limite"), (201, 0, "limite"), (10, -1, "deslocamento")],
)
def test_limite_acima_de_200_ou_invalido_e_recusado(
    conexao, carregado, limite, deslocamento, campo
):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        servico.listar_registros(
            conexao, carregado.formulario.id, limite=limite, deslocamento=deslocamento
        )

    # assert
    assert [e.campo for e in excecao.value.erros] == [campo]


def test_limite_de_200_e_aceito(conexao, carregado):
    # act / assert
    assert servico.listar_registros(conexao, carregado.formulario.id, limite=200).total == 3


# --- filtros ---


def test_filtros_por_selecao_sim_nao_texto_e_calculado_booleano(conexao, carregado):
    # act
    def por(**filtros):
        return servico.listar_registros(conexao, carregado.formulario.id, filtros=filtros).total

    # assert
    assert por(resultado="OK") == 2
    assert por(ensaiado=True) == 2 and por(ensaiado=False) == 1
    assert por(obs="beta") == 1
    assert por(alto=True) == 1  # 12,34 * ... carga > 10; os demais não


@pytest.mark.parametrize(
    ("texto", "esperados"),
    [("true", 2), ("sim", 2), ("Sim", 2), ("false", 1), ("não", 1), ("nao", 1)],
)
def test_sim_nao_aceita_texto_vindo_da_url(conexao, carregado, texto, esperados):
    # act
    listagem = servico.listar_registros(
        conexao, carregado.formulario.id, filtros={"ensaiado": texto}
    )

    # assert
    assert listagem.total == esperados


def test_filtros_combinam_com_e(conexao, carregado):
    # act
    listagem = servico.listar_registros(
        conexao,
        carregado.formulario.id,
        filtros={"resultado": "OK", "ensaiado": True, "obs": "alfa"},
    )

    # assert
    assert listagem.total == 1


@pytest.mark.parametrize("campo", ["carga", "dia", "dobro", "local", "secao_a", "inexistente"])
def test_campo_que_nao_aceita_filtro_de_igualdade_e_recusado(conexao, carregado, campo):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        servico.listar_registros(conexao, carregado.formulario.id, filtros={campo: "x"})

    # assert
    assert [e.campo for e in excecao.value.erros] == [campo]


def test_valor_de_filtro_invalido_para_sim_nao_e_recusado(conexao, carregado):
    # act / assert
    with pytest.raises(RegistroInvalido):
        servico.listar_registros(conexao, carregado.formulario.id, filtros={"ensaiado": "talvez"})


@pytest.mark.parametrize(
    "campo", ["a') OR 1=1 --", 'x"; DROP TABLE registros; --', "$.dados", "resultado' --"]
)
def test_tentativa_de_injecao_no_nome_do_campo_e_recusada_e_nada_e_apagado(
    conexao, carregado, campo
):
    # act
    with pytest.raises(RegistroInvalido):
        servico.listar_registros(conexao, carregado.formulario.id, filtros={campo: "OK"})

    # assert
    assert servico.listar_registros(conexao, carregado.formulario.id).total == 3


@pytest.mark.parametrize("valor", ["' OR '1'='1", "OK'; DROP TABLE registros; --", "%"])
def test_tentativa_de_injecao_no_valor_so_nao_encontra_nada(conexao, carregado, valor):
    # act
    listagem = servico.listar_registros(
        conexao, carregado.formulario.id, filtros={"resultado": valor}
    )

    # assert
    assert listagem.total == 0
    assert servico.listar_registros(conexao, carregado.formulario.id).total == 3


def test_filtro_por_data_de_criacao_inclui_o_dia_inteiro_dos_dois_limites(conexao, criado):
    # arrange
    for dias in (0, 1, 2):
        _novo(conexao, criado, {}, AGORA + timedelta(days=dias, hours=13))  # 23:00 de cada dia

    # act
    def total(**janela):
        return servico.listar_registros(conexao, criado.formulario.id, **janela).total

    # assert
    assert total(criado_de=date(2026, 11, 3), criado_ate=date(2026, 11, 3)) == 1
    assert total(criado_de=date(2026, 11, 3)) == 2
    assert total(criado_ate=date(2026, 11, 3)) == 2
    assert total(criado_de=date(2026, 11, 2), criado_ate=date(2026, 11, 4)) == 3
    assert total(criado_de=date(2026, 12, 1)) == 0


# --- exportação CSV ---


def test_exportacao_traz_cabecalho_com_unidade_numeros_arredondados_e_virgula(conexao, carregado):
    # act
    texto = servico.exportar_csv(conexao, carregado.formulario.id).decode("utf-8-sig")
    linhas = texto.split("\r\n")

    # assert
    assert linhas[0] == "Resultado;Ensaiado?;Observação;Carga (kN);Dia;Dobro;Alto?;Local"
    assert "OK;Sim;alfa;12,3;2026-11-01;24,7;Sim;" in linhas[3]  # o mais antigo é o último


def test_exportacao_comeca_com_bom_e_neutraliza_texto_mas_nao_numero_negativo(conexao, carregado):
    # act
    bruto = servico.exportar_csv(conexao, carregado.formulario.id)
    texto = bruto.decode("utf-8-sig")

    # assert
    assert bruto.startswith(b"\xef\xbb\xbf")
    assert "'=cmd|' /C calc'!A0" in texto  # texto de usuário neutralizado
    assert ";-3,5;" in texto  # número negativo intacto


def test_exportacao_com_calculado_com_erro_e_vazio(conexao, criado):
    # arrange
    com_erro = servico.criar_formulario(
        conexao,
        "dividir",
        {
            "campos": [
                {"id": "d", "tipo": "numero", "rotulo": "D"},
                {"id": "inv", "tipo": "calculado", "rotulo": "Inv", "formula": "1 / d"},
            ]
        },
        AGORA,
    )
    servico.criar_registro(conexao, com_erro.formulario.id, com_erro.versao.id, {"d": 0}, AGORA)
    servico.criar_registro(conexao, com_erro.formulario.id, com_erro.versao.id, {}, AGORA)

    # act
    linhas = servico.exportar_csv(conexao, com_erro.formulario.id).decode("utf-8-sig").split("\r\n")

    # assert: o mais recente primeiro (vazio), depois o de erro
    assert linhas[1] == ";" and linhas[2].startswith("0;ERRO: Divisão por zero")


def test_exportacao_usa_a_mesma_versao_e_os_mesmos_filtros_da_listagem(conexao, carregado):
    # arrange
    filtros = {"resultado": "OK"}

    # act
    listagem = servico.listar_registros(conexao, carregado.formulario.id, filtros=filtros)
    linhas = (
        servico.exportar_csv(conexao, carregado.formulario.id, filtros=filtros)
        .decode("utf-8-sig")
        .split("\r\n")
    )

    # assert: cabeçalho + uma linha por registro filtrado + o "" final
    assert len(linhas) == 1 + listagem.total + 1
    assert not any("beta" in linha for linha in linhas)


def test_exportacao_de_versao_antiga_usa_as_colunas_dela(conexao, carregado):
    # arrange
    servico.publicar_versao(
        conexao,
        carregado.formulario.id,
        {"campos": [{"id": "x", "tipo": "texto", "rotulo": "X"}]},
        AGORA,
    )

    # act
    antiga = servico.exportar_csv(conexao, carregado.formulario.id, versao_id=carregado.versao.id)
    atual = servico.exportar_csv(conexao, carregado.formulario.id)

    # assert
    assert antiga.decode("utf-8-sig").startswith("Resultado;")
    assert atual.decode("utf-8-sig") == "X\r\n"


def test_exportacao_rejeita_filtro_invalido_como_a_listagem(conexao, carregado):
    # act / assert
    with pytest.raises(RegistroInvalido):
        servico.exportar_csv(conexao, carregado.formulario.id, filtros={"carga": "5"})


def test_exportacao_junta_todas_as_paginas(conexao, criado):
    # arrange: mais registros do que cabe numa página de 200
    for _ in range(205):
        _novo(conexao, criado, {})

    # act
    linhas = servico.exportar_csv(conexao, criado.formulario.id).decode("utf-8-sig").split("\r\n")

    # assert
    assert len(linhas) == 1 + 205 + 1
