import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from forms import servico
from forms.ia.cliente import ClienteFalso, IaIndisponivel
from forms.ia.resumo import calcular_agregados, resumir
from forms.ia.validacao import (
    ResumoRejeitado,
    conferir_numeros,
    extrair_numeros,
    validar_resumo,
)
from forms.models import ValorInvalido

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
D = Decimal

DEFINICAO = {
    "campos": [
        {"id": "obra", "tipo": "texto", "rotulo": "Obra"},
        {"id": "fase", "tipo": "selecao", "rotulo": "Fase", "opcoes": ["Cura", "Ruptura"]},
        {"id": "ok", "tipo": "sim_nao", "rotulo": "Ensaiado?"},
        {"id": "carga", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
        {
            "id": "dobro",
            "tipo": "calculado",
            "rotulo": "Dobro",
            "formula": "carga * 2",
            "casas_decimais": 1,
        },
        {"id": "alta", "tipo": "calculado", "rotulo": "Carga alta?", "formula": "carga > 100"},
        {"id": "inverso", "tipo": "calculado", "rotulo": "Inverso", "formula": "1 / carga"},
    ]
}


@pytest.fixture
def formulario(conexao):
    criado = servico.criar_formulario(conexao, "ensaios", DEFINICAO, AGORA)
    registros = [
        {"obra": "SEGREDO-DO-CLIENTE", "fase": "Cura", "ok": True, "carga": "100"},
        {"obra": "Obra B", "fase": "Cura", "ok": True, "carga": "150.5"},
        {"obra": "Obra C", "fase": "Ruptura", "ok": False, "carga": "0"},  # 1/0 => erro de cálculo
        {"obra": "Obra D", "fase": "Ruptura", "ok": True},  # carga vazia
    ]
    for dados in registros:
        servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, dados, AGORA)
    return criado


def _resumo(titulo="Resumo", paragrafos=("Texto sem números.",), destaques=()):
    return json.dumps(
        {"titulo": titulo, "paragrafos": list(paragrafos), "destaques": list(destaques)}
    )


# --- agregados: calculados pelo código ---


def test_contagem_e_estatisticas_dos_numeros_ignoram_vazios(conexao, formulario):
    # act
    agregados = calcular_agregados(conexao, formulario.formulario.id)

    # assert
    assert agregados.total == 4
    carga = agregados.coluna("carga")
    assert (carga.n, carga.minimo, carga.maximo, carga.soma) == (3, D("0"), D("150.5"), D("250.5"))
    assert carga.media == D("250.5") / 3 and carga.vazios == 1


def test_frequencia_de_selecao_e_sim_nao(conexao, formulario):
    # act
    agregados = calcular_agregados(conexao, formulario.formulario.id)

    # assert
    assert agregados.coluna("fase").frequencias == {"Cura": 2, "Ruptura": 2}
    assert agregados.coluna("ok").frequencias == {"Sim": 3, "Não": 1}


def test_calculado_numerico_agrega_so_os_valores_e_conta_os_erros(conexao, formulario):
    # act
    inverso = calcular_agregados(conexao, formulario.formulario.id).coluna("inverso")

    # assert: 1/100 e 1/150.5 calculam; 1/0 é erro; carga vazia fica vazia
    assert inverso.n == 2 and inverso.erros == 1 and inverso.vazios == 1
    assert inverso.minimo == D("1") / D("150.5") and inverso.maximo == D("0.01")


def test_calculado_booleano_conta_verdadeiro_falso_e_vazio(conexao, formulario):
    # act
    alta = calcular_agregados(conexao, formulario.formulario.id).coluna("alta")

    # assert
    assert alta.frequencias == {"Sim": 1, "Não": 2} and alta.vazios == 1


def test_texto_nao_entra_nos_agregados(conexao, formulario):
    # act
    agregados = calcular_agregados(conexao, formulario.formulario.id)

    # assert: o texto livre (que pode ter dado do cliente) nunca é agregado nem enviado
    assert [c.id for c in agregados.colunas] == ["fase", "ok", "carga", "dobro", "alta", "inverso"]


def test_agrega_todos_os_registros_mesmo_alem_de_uma_pagina(conexao):
    # arrange: mais registros do que cabe numa página de 200
    criado = servico.criar_formulario(
        conexao, "muitos", {"campos": [{"id": "n", "tipo": "numero", "rotulo": "N"}]}, AGORA
    )
    for _ in range(205):
        servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, {"n": "1"}, AGORA)

    # act
    agregados = calcular_agregados(conexao, criado.formulario.id)

    # assert
    assert agregados.total == 205 and agregados.coluna("n").soma == D("205")


def test_respeita_os_filtros_da_listagem(conexao, formulario):
    # act
    agregados = calcular_agregados(conexao, formulario.formulario.id, filtros={"fase": "Ruptura"})

    # assert
    assert agregados.total == 2 and agregados.coluna("carga").n == 1


def test_numeros_permitidos_trazem_contagens_estatisticas_e_percentuais(conexao, formulario):
    # act
    permitidos = calcular_agregados(conexao, formulario.formulario.id).numeros_permitidos()

    # assert
    assert {
        D("4"),
        D("3"),
        D("150.5"),
        D("250.5"),
        D("50"),
        D("75"),
    } <= permitidos  # 2/4 e 3/4 em %


# --- extração e conferência de números ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("A carga média foi de 25,5 kN.", [(D("25.5"), 1)]),
        ("Foram 1.234 registros.", [(D("1234"), 0)]),
        ("Média de 1.234,56.", [(D("1234.56"), 2)]),
        ("Valor 25.5 com ponto.", [(D("25.5"), 1)]),
        ("12% dos casos e 3 registros", [(D("12"), 0), (D("3"), 0)]),
        ("Sem números aqui.", []),
        ("Entre 10 e 20", [(D("10"), 0), (D("20"), 0)]),
        ("-3,5 de variação", [(D("-3.5"), 1)]),
        ("de 10-20 kN", [(D("10"), 0), (D("20"), 0)]),
    ],
)
def test_extrai_numeros_em_formato_brasileiro(texto, esperado):
    # act / assert
    assert extrair_numeros(texto) == esperado


def test_data_no_texto_nao_passa_na_conferencia():
    # act
    erros = conferir_numeros("Em 2026-11-02 aconteceu", {D("4")})

    # assert: o resumo não deve citar datas; os pedaços dela não são agregados
    assert "2026" in erros


def test_o_sinal_negativo_faz_parte_do_numero_conferido():
    # act / assert
    assert conferir_numeros("mínimo de -3,5", {D("-3.5")}) == []
    assert conferir_numeros("mínimo de -3,5", {D("3.5")}) != []
    assert conferir_numeros("máximo de 3,5", {D("-3.5")}) != []


def test_numero_confere_quando_igual_ou_arredondado_para_as_casas_escritas():
    # arrange
    permitidos = {D("25.4647908947"), D("4"), D("150.5")}

    # act / assert
    assert conferir_numeros("25,46 kN e 25,5 e 25 e 4 e 150,5", permitidos) == []


@pytest.mark.parametrize("texto", ["25,47 kN", "5 registros", "150,6", "3"])
def test_numero_que_nao_bate_com_nenhum_agregado_e_apontado(texto):
    # arrange
    permitidos = {D("25.4647908947"), D("4"), D("150.5")}

    # act
    erros = conferir_numeros(texto, permitidos)

    # assert
    assert len(erros) == 1


def test_arredondamento_usa_meio_para_cima_como_o_resto_do_sistema():
    # act / assert: 0,25 -> 0,3 (e não 0,2 do meio-par)
    assert conferir_numeros("0,3", {D("0.25")}) == []
    assert conferir_numeros("0,2", {D("0.25")}) != []


# --- validar a saída do LLM (dado não confiável) ---


def _permitidos():
    return {D("4"), D("3"), D("150.5")}


def test_resumo_valido_com_numeros_que_batem_passa():
    # act
    resumo = validar_resumo(
        _resumo("Ensaios", ["Foram 4 registros, 3 com carga, maior de 150,5 kN."], ["4 no total"]),
        _permitidos(),
    )

    # assert
    assert resumo.titulo == "Ensaios" and resumo.destaques == ("4 no total",)
    assert resumo.paragrafos == ("Foram 4 registros, 3 com carga, maior de 150,5 kN.",)


def test_numero_errado_rejeita_o_resumo_inteiro_citando_o_numero():
    # act
    with pytest.raises(ResumoRejeitado) as excecao:
        validar_resumo(_resumo(paragrafos=["Foram 5 registros."]), _permitidos())

    # assert
    assert "5" in str(excecao.value) and "não confere" in str(excecao.value)


def test_numero_errado_no_titulo_ou_nos_destaques_tambem_rejeita():
    # act / assert
    with pytest.raises(ResumoRejeitado):
        validar_resumo(_resumo(titulo="99 ensaios"), _permitidos())
    with pytest.raises(ResumoRejeitado):
        validar_resumo(_resumo(destaques=["Carga de 200 kN"]), _permitidos())


@pytest.mark.parametrize(
    "saida",
    [
        "não é json",
        "[]",
        "{}",
        '{"titulo": "x"}',
        '{"titulo": 5, "paragrafos": ["a"], "destaques": []}',
        '{"titulo": "x", "paragrafos": "a", "destaques": []}',
        '{"titulo": "x", "paragrafos": [], "destaques": []}',
        '{"titulo": "x", "paragrafos": [1], "destaques": []}',
        '{"titulo": "x", "paragrafos": ["a"], "destaques": "b"}',
        '{"titulo": "x", "paragrafos": ["a"], "destaques": [], "extra": 1}',
        '{"titulo": "", "paragrafos": ["a"], "destaques": []}',
    ],
)
def test_json_fora_do_esquema_e_rejeitado(saida):
    # act / assert
    with pytest.raises(ResumoRejeitado):
        validar_resumo(saida, _permitidos())


def test_limites_de_tamanho_evitam_resposta_gigante():
    # act / assert
    with pytest.raises(ResumoRejeitado):
        validar_resumo(_resumo(titulo="x" * 500), _permitidos())
    with pytest.raises(ResumoRejeitado):
        validar_resumo(_resumo(paragrafos=["a"] * 20), _permitidos())
    with pytest.raises(ResumoRejeitado):
        validar_resumo(_resumo(paragrafos=["a" * 5000]), _permitidos())


def test_aceita_json_dentro_de_bloco_de_codigo():
    # act
    resumo = validar_resumo("```json\n" + _resumo() + "\n```", _permitidos())

    # assert
    assert resumo.titulo == "Resumo"


# --- o fluxo completo, com o cliente falso ---


def test_resumo_correto_passa_e_volta_com_os_agregados_calculados_pelo_codigo(conexao, formulario):
    # arrange
    cliente = ClienteFalso([_resumo("Ensaios", ["Há 4 registros e a maior carga é 150,5 kN."])])

    # act
    gerado = resumir(conexao, cliente, formulario.formulario.id)

    # assert
    assert gerado.resumo.titulo == "Ensaios" and gerado.agregados.total == 4


def test_resumo_com_numero_errado_do_llm_e_rejeitado(conexao, formulario):
    # arrange: o LLM errou a contagem
    cliente = ClienteFalso([_resumo(paragrafos=["Há 7 registros."])])

    # act / assert
    with pytest.raises(ResumoRejeitado):
        resumir(conexao, cliente, formulario.formulario.id)


def test_o_prompt_leva_so_agregados_e_nunca_registros_nem_texto_livre(conexao, formulario):
    # arrange
    cliente = ClienteFalso([_resumo()])

    # act
    resumir(conexao, cliente, formulario.formulario.id)

    # assert
    sistema, mensagem = cliente.chamadas[0]
    assert "SEGREDO-DO-CLIENTE" not in sistema + mensagem and "Obra B" not in mensagem
    assert '"total": 4' in mensagem and "150.5" in mensagem and "kN" in mensagem


def test_o_sistema_proibe_calcular_e_manda_citar_so_os_numeros_dados(conexao, formulario):
    # arrange
    cliente = ClienteFalso([_resumo()])

    # act
    resumir(conexao, cliente, formulario.formulario.id)

    # assert
    sistema = cliente.chamadas[0][0].lower()
    assert "não calcule" in sistema and "somente os números" in sistema and "datas" in sistema


def test_sem_registros_nao_chama_o_llm(conexao):
    # arrange
    criado = servico.criar_formulario(conexao, "vazio", {"campos": []}, AGORA)
    cliente = ClienteFalso([])

    # act / assert
    with pytest.raises(ValorInvalido, match="registros"):
        resumir(conexao, cliente, criado.formulario.id)
    assert cliente.chamadas == []


def test_sem_chave_levanta_ia_indisponivel(conexao, formulario):
    # arrange
    cliente = ClienteFalso([IaIndisponivel("sem chave")])

    # act / assert
    with pytest.raises(IaIndisponivel):
        resumir(conexao, cliente, formulario.formulario.id)


def test_nada_e_gravado(conexao, formulario):
    # arrange
    antes = conexao.execute("SELECT COUNT(*) FROM registros").fetchone()[0]

    # act
    resumir(conexao, ClienteFalso([_resumo()]), formulario.formulario.id)

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM registros").fetchone()[0] == antes
