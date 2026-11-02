from datetime import date
from decimal import Decimal

import pytest

from forms.models import Campo, TipoCampo, ValorInvalido
from forms.tipos_campo import (
    ESPECIFICACOES,
    PROPRIEDADES_COMUNS,
    Localizacao,
    eh_vazio,
    especificacao_do_tipo,
    normalizar_valor,
    valor_para_json,
)

D = Decimal


def _campo(tipo: TipoCampo, opcoes: tuple[str, ...] = (), maximo: int | None = None) -> Campo:
    return Campo(id="c", tipo=tipo, rotulo="C", opcoes=opcoes, maximo=maximo)


# --- regra única de "vazio" ---


@pytest.mark.parametrize("valor", [None, ""])
def test_none_e_string_vazia_sao_vazios(valor: object):
    # act / assert
    assert eh_vazio(valor) is True


@pytest.mark.parametrize("valor", [0, 0.0, False, " ", "0", "a", [], {}])
def test_zero_falso_e_espaco_nao_sao_vazios(valor: object):
    # act / assert
    assert eh_vazio(valor) is False


@pytest.mark.parametrize(
    "tipo",
    [
        TipoCampo.TEXTO,
        TipoCampo.NUMERO,
        TipoCampo.DATA,
        TipoCampo.SELECAO,
        TipoCampo.SIM_NAO,
        TipoCampo.REFERENCIA,
        TipoCampo.LOCALIZACAO,
        TipoCampo.FOTO,
    ],
)
@pytest.mark.parametrize("vazio", [None, ""])
def test_vazio_em_cada_tipo_normaliza_para_none(tipo: TipoCampo, vazio: object):
    # arrange
    campo = _campo(tipo, ("A",))

    # act / assert
    assert normalizar_valor(campo, vazio) is None


# --- numero ---


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (25, Decimal("25")),
        (25.5, Decimal("25.5")),
        ("25.50", Decimal("25.50")),
        ("-3.5", Decimal("-3.5")),
        ("+7", Decimal("7")),
        (" 12.5 ", Decimal("12.5")),
        (0, Decimal("0")),
    ],
)
def test_numero_aceita_numero_json_ou_string(entrada: object, esperado: Decimal):
    # act
    resultado = normalizar_valor(_campo(TipoCampo.NUMERO), entrada)

    # assert
    assert resultado == esperado


def test_float_vira_decimal_sem_ruido_binario():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.NUMERO), 0.1)

    # assert
    assert resultado == Decimal("0.1")
    assert resultado != Decimal(0.1)  # Decimal(float) carregaria o ruído binário


def test_numero_preserva_as_casas_digitadas():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.NUMERO), "25.50")

    # assert
    assert valor_para_json(resultado) == "25.50"


def test_numero_com_expoente_sai_em_notacao_comum():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.NUMERO), 1e22)

    # assert
    assert valor_para_json(resultado) == "10000000000000000000000"


@pytest.mark.parametrize(
    "entrada",
    [
        "abc",
        "1,5",
        "1_000",
        "NaN",
        "Infinity",
        "-Infinity",
        "1e3",
        "١٢٣",
        "--1",
        "1.",
        ".5",
        "0x10",
    ],
)
def test_numero_invalido_em_string_e_rejeitado(entrada: str):
    # act / assert
    with pytest.raises(ValorInvalido, match="número"):
        normalizar_valor(_campo(TipoCampo.NUMERO), entrada)


@pytest.mark.parametrize("entrada", [True, False, float("nan"), float("inf"), [1], {"a": 1}])
def test_numero_rejeita_booleano_nao_finito_e_estruturas(entrada: object):
    # act / assert
    with pytest.raises(ValorInvalido, match="número"):
        normalizar_valor(_campo(TipoCampo.NUMERO), entrada)


# --- data ---


def test_data_iso_valida_e_aceita():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.DATA), "2026-11-01")

    # assert
    assert resultado == date(2026, 11, 1)
    assert valor_para_json(resultado) == "2026-11-01"


def test_data_bissexta_existe_e_nao_bissexta_nao():
    # act / assert
    assert normalizar_valor(_campo(TipoCampo.DATA), "2024-02-29") == date(2024, 2, 29)
    with pytest.raises(ValorInvalido, match="data"):
        normalizar_valor(_campo(TipoCampo.DATA), "2026-02-29")


@pytest.mark.parametrize(
    "entrada",
    ["2026-13-01", "2026-00-10", "0000-01-01", "01/11/2026", "20261101", "2026-W44-1", "2026-1-1"]
    + ["2026-11-01T10:00:00", " 2026-11-01", "abc", "٢٠٢٦-١١-٠١"],
)
def test_data_fora_do_formato_iso_ou_inexistente_e_rejeitada(entrada: str):
    # act / assert
    with pytest.raises(ValorInvalido, match="data"):
        normalizar_valor(_campo(TipoCampo.DATA), entrada)


@pytest.mark.parametrize("entrada", [20261101, True, 1.5, ["2026-11-01"]])
def test_data_que_nao_e_texto_e_rejeitada(entrada: object):
    # act / assert
    with pytest.raises(ValorInvalido, match="data"):
        normalizar_valor(_campo(TipoCampo.DATA), entrada)


# --- selecao ---


def test_selecao_aceita_opcao_da_lista():
    # arrange
    campo = _campo(TipoCampo.SELECAO, ("Aprovado", "Reprovado"))

    # act / assert
    assert normalizar_valor(campo, "Aprovado") == "Aprovado"


def test_selecao_rejeita_opcao_fora_da_lista_citando_as_validas():
    # arrange
    campo = _campo(TipoCampo.SELECAO, ("Aprovado", "Reprovado"))

    # act
    with pytest.raises(ValorInvalido) as excecao:
        normalizar_valor(campo, "Talvez")

    # assert
    assert "Aprovado" in str(excecao.value) and "Reprovado" in str(excecao.value)


def test_selecao_diferencia_maiusculas_de_minusculas():
    # arrange
    campo = _campo(TipoCampo.SELECAO, ("Aprovado",))

    # act / assert
    with pytest.raises(ValorInvalido):
        normalizar_valor(campo, "aprovado")


@pytest.mark.parametrize("entrada", [1, True, ["Aprovado"]])
def test_selecao_que_nao_e_texto_e_rejeitada(entrada: object):
    # arrange
    campo = _campo(TipoCampo.SELECAO, ("Aprovado",))

    # act / assert
    with pytest.raises(ValorInvalido):
        normalizar_valor(campo, entrada)


# --- sim_nao e texto ---


@pytest.mark.parametrize("entrada", [True, False])
def test_sim_nao_aceita_booleano(entrada: bool):
    # act / assert
    assert normalizar_valor(_campo(TipoCampo.SIM_NAO), entrada) is entrada


@pytest.mark.parametrize("entrada", ["true", "sim", 1, 0, "False"])
def test_sim_nao_rejeita_o_que_nao_e_booleano(entrada: object):
    # act / assert
    with pytest.raises(ValorInvalido, match="sim ou não"):
        normalizar_valor(_campo(TipoCampo.SIM_NAO), entrada)


def test_texto_aceita_string_sem_alterar():
    # act / assert
    assert normalizar_valor(_campo(TipoCampo.TEXTO), "  Obra A ") == "  Obra A "


@pytest.mark.parametrize("entrada", [1, True, ["a"]])
def test_texto_rejeita_o_que_nao_e_string(entrada: object):
    # act / assert
    with pytest.raises(ValorInvalido, match="texto"):
        normalizar_valor(_campo(TipoCampo.TEXTO), entrada)


# --- tipos sem valor de entrada tratado aqui ---


@pytest.mark.parametrize(
    "tipo",
    [TipoCampo.CALCULADO, TipoCampo.SECAO],
)
def test_tipo_que_nao_recebe_valor_do_cliente_e_erro_explicito(tipo: TipoCampo):
    # act / assert
    with pytest.raises(ValorInvalido, match="não recebe valor"):
        normalizar_valor(_campo(tipo), "x")


# --- tabela de tipos ---


def test_toda_a_enumeracao_de_tipos_tem_especificacao():
    # assert
    assert set(ESPECIFICACOES) == set(TipoCampo)


def test_especificacao_traz_rotulo_em_portugues_e_propriedades():
    # act
    especificacao = especificacao_do_tipo("numero")

    # assert
    assert especificacao.tipo is TipoCampo.NUMERO
    assert especificacao.rotulo == "Número"
    assert {"unidade", "casas_decimais", "obrigatorio"} <= set(especificacao.propriedades)


def test_propriedades_exclusivas_de_cada_tipo():
    # assert
    assert "opcoes" in especificacao_do_tipo("selecao").propriedades
    assert "formula" in especificacao_do_tipo("calculado").propriedades
    assert "formulario" in especificacao_do_tipo("referencia").propriedades
    assert "maximo" in especificacao_do_tipo("foto").propriedades
    assert "opcoes" not in especificacao_do_tipo("texto").propriedades


def test_secao_e_referencia_nao_aceitam_compartilhado():
    # assert
    assert "compartilhado" not in especificacao_do_tipo("secao").propriedades
    assert "compartilhado" not in especificacao_do_tipo("referencia").propriedades
    assert "compartilhado" in especificacao_do_tipo("numero").propriedades


def test_propriedades_comuns_nao_se_repetem_na_especificacao():
    # assert
    for especificacao in ESPECIFICACOES.values():
        assert set(especificacao.propriedades).isdisjoint(PROPRIEDADES_COMUNS)


def test_tipo_desconhecido_gera_erro_explicito():
    # act
    with pytest.raises(ValorInvalido) as excecao:
        especificacao_do_tipo("telefone")

    # assert
    assert "telefone" in str(excecao.value)


# --- localizacao ---


def test_localizacao_valida_vira_par_de_decimais_e_volta_como_strings():
    # arrange
    campo = _campo(TipoCampo.LOCALIZACAO)

    # act
    resultado = normalizar_valor(campo, {"latitude": "-23.550520", "longitude": -46.633308})

    # assert
    assert resultado == Localizacao(D("-23.550520"), D("-46.633308"))
    assert valor_para_json(resultado) == {"latitude": "-23.550520", "longitude": "-46.633308"}


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [("90", "180"), ("-90", "-180"), ("0", "0"), ("89.999999", "-179.999999")],
)
def test_localizacao_aceita_os_limites_da_faixa(latitude: str, longitude: str):
    # act / assert
    campo = _campo(TipoCampo.LOCALIZACAO)
    assert normalizar_valor(campo, {"latitude": latitude, "longitude": longitude}) is not None


@pytest.mark.parametrize(
    ("latitude", "longitude", "trecho"),
    [
        ("90.000001", "0", "latitude"),
        ("-91", "0", "latitude"),
        ("0", "180.1", "longitude"),
        ("0", "-181", "longitude"),
        ("abc", "0", "latitude"),
        ("0", "NaN", "longitude"),
        (True, "0", "latitude"),
        ([1], "0", "latitude"),
    ],
)
def test_localizacao_fora_da_faixa_ou_invalida_e_rejeitada(
    latitude: object, longitude: object, trecho: str
):
    # act
    with pytest.raises(ValorInvalido) as excecao:
        normalizar_valor(
            _campo(TipoCampo.LOCALIZACAO), {"latitude": latitude, "longitude": longitude}
        )

    # assert
    assert trecho in str(excecao.value)


@pytest.mark.parametrize(
    "valor",
    [
        {"latitude": "10"},
        {"longitude": "10"},
        {"latitude": "10", "longitude": ""},
        {"latitude": None, "longitude": "5"},
    ],
)
def test_localizacao_com_so_um_dos_dois_e_rejeitada(valor: dict[str, object]):
    # act / assert
    with pytest.raises(ValorInvalido, match="latitude e longitude"):
        normalizar_valor(_campo(TipoCampo.LOCALIZACAO), valor)


def test_localizacao_com_os_dois_vazios_e_vazia():
    # act / assert
    assert normalizar_valor(_campo(TipoCampo.LOCALIZACAO), {}) is None
    assert (
        normalizar_valor(_campo(TipoCampo.LOCALIZACAO), {"latitude": "", "longitude": None}) is None
    )


@pytest.mark.parametrize(
    "valor", ["-23,5 / -46,6", [1, 2], 5, {"latitude": "1", "longitude": "2", "z": "3"}]
)
def test_localizacao_que_nao_e_um_par_latitude_longitude_e_rejeitada(valor: object):
    # act / assert
    with pytest.raises(ValorInvalido):
        normalizar_valor(_campo(TipoCampo.LOCALIZACAO), valor)


# --- foto ---


def test_foto_aceita_lista_de_ids_de_anexo():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.FOTO), [3, 1, 2])

    # assert
    assert resultado == (3, 1, 2)
    assert valor_para_json(resultado) == [3, 1, 2]


def test_foto_com_lista_vazia_e_vazia():
    # act / assert
    assert normalizar_valor(_campo(TipoCampo.FOTO), []) is None


def test_foto_respeita_o_maximo():
    # arrange
    campo = _campo(TipoCampo.FOTO, maximo=2)

    # act / assert
    assert normalizar_valor(campo, [1, 2]) == (1, 2)
    with pytest.raises(ValorInvalido, match="no máximo 2"):
        normalizar_valor(campo, [1, 2, 3])


@pytest.mark.parametrize("valor", ["1", 1, [1, "2"], [0], [-1], [True], [1.5], [1, 1], {"a": 1}])
def test_foto_exige_lista_de_ids_inteiros_positivos_sem_repeticao(valor: object):
    # act / assert
    with pytest.raises(ValorInvalido):
        normalizar_valor(_campo(TipoCampo.FOTO), valor)


# --- referencia ---


def test_referencia_aceita_o_id_do_registro_de_origem():
    # act
    resultado = normalizar_valor(_campo(TipoCampo.REFERENCIA), 42)

    # assert
    assert resultado == 42
    assert valor_para_json(resultado) == 42


@pytest.mark.parametrize("valor", ["42", 1.5, 0, -3, True, [1]])
def test_referencia_exige_inteiro_positivo(valor: object):
    # act / assert
    with pytest.raises(ValorInvalido, match="referência"):
        normalizar_valor(_campo(TipoCampo.REFERENCIA), valor)
