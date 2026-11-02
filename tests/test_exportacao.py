from forms.exportacao import Coluna, formatar_celula, gerar_csv
from forms.formulas import TipoFormula
from forms.models import Registro, TipoCampo

N, DT, B = TipoFormula.NUMERO, TipoFormula.DATA, TipoFormula.BOOLEANO


def _coluna(
    tipo: TipoCampo, id: str = "c", rotulo: str = "Campo", unidade=None, casas=None, formula=None
):
    return Coluna(
        id=id,
        rotulo=rotulo,
        unidade=unidade,
        tipo=tipo,
        casas_decimais=casas,
        tipo_na_formula=formula,
    )


def _registro(id: int, dados: dict) -> Registro:
    return Registro(id, 1, 1, dados, "2026-11-02T10:00:00+00:00", "2026-11-02T10:00:00+00:00")


# --- números ---


def test_numero_sai_com_virgula_decimal_e_arredondado_pelas_casas():
    # arrange
    coluna = _coluna(TipoCampo.NUMERO, casas=1)

    # act / assert
    assert formatar_celula(coluna, "25.46479") == "25,5"
    assert formatar_celula(coluna, "25.44") == "25,4"
    assert formatar_celula(coluna, "25") == "25,0"


def test_arredondamento_e_meio_para_cima_como_o_usuario_espera():
    # arrange
    coluna = _coluna(TipoCampo.NUMERO, casas=1)

    # act / assert: 0,25 -> 0,3 (o padrão do Decimal, meio-par, daria 0,2)
    assert formatar_celula(coluna, "0.25") == "0,3"
    assert formatar_celula(coluna, "-0.25") == "-0,3"


def test_numero_sem_casas_decimais_sai_com_o_valor_completo():
    # arrange
    coluna = _coluna(TipoCampo.NUMERO)

    # act / assert
    assert formatar_celula(coluna, "25.4647908947") == "25,4647908947"
    assert formatar_celula(coluna, "25.50") == "25,50"


def test_numero_negativo_nao_e_corrompido_pela_neutralizacao():
    # arrange: "-3,5" começa com "-", mas é número e não pode virar "'-3,5"
    coluna = _coluna(TipoCampo.NUMERO, casas=1)

    # act / assert
    assert formatar_celula(coluna, "-3.5") == "-3,5"


def test_zero_negativo_depois_de_arredondar_sai_sem_sinal():
    # arrange
    coluna = _coluna(TipoCampo.NUMERO, casas=1)

    # act / assert
    assert formatar_celula(coluna, "-0.04") == "0,0"


def test_numero_enorme_com_muitas_casas_nao_estoura_a_precisao():
    # arrange
    coluna = _coluna(TipoCampo.NUMERO, casas=10)

    # act / assert
    assert (
        formatar_celula(coluna, "1234567890123456789012345.5")
        == "1234567890123456789012345,5000000000"
    )


def test_notacao_cientifica_nunca_aparece():
    # act / assert
    assert formatar_celula(_coluna(TipoCampo.NUMERO), "1E+3") == "1000"


# --- calculado ---


def test_calculado_numerico_arredonda_pelas_casas_decimais():
    # arrange
    coluna = _coluna(TipoCampo.CALCULADO, casas=1, formula=N)

    # act / assert
    assert formatar_celula(coluna, {"valor": "25.46479", "erro": None}) == "25,5"


def test_calculado_booleano_e_de_data():
    # act / assert
    assert (
        formatar_celula(_coluna(TipoCampo.CALCULADO, formula=B), {"valor": True, "erro": None})
        == "Sim"
    )
    assert (
        formatar_celula(_coluna(TipoCampo.CALCULADO, formula=B), {"valor": False, "erro": None})
        == "Não"
    )
    assert (
        formatar_celula(
            _coluna(TipoCampo.CALCULADO, formula=DT), {"valor": "2026-11-29", "erro": None}
        )
        == "2026-11-29"
    )


def test_calculado_com_erro_sai_como_erro_e_vazio_sai_vazio():
    # arrange
    coluna = _coluna(TipoCampo.CALCULADO, formula=N)

    # act / assert
    assert (
        formatar_celula(coluna, {"valor": None, "erro": "Divisão por zero."})
        == "ERRO: Divisão por zero."
    )
    assert formatar_celula(coluna, {"valor": None, "erro": None}) == ""


def test_calculado_ausente_no_registro_antigo_sai_vazio():
    # act / assert
    assert formatar_celula(_coluna(TipoCampo.CALCULADO, formula=N), None) == ""


# --- outros tipos ---


def test_sim_nao_data_referencia_e_vazios():
    # act / assert
    assert formatar_celula(_coluna(TipoCampo.SIM_NAO), True) == "Sim"
    assert formatar_celula(_coluna(TipoCampo.SIM_NAO), False) == "Não"
    assert formatar_celula(_coluna(TipoCampo.SIM_NAO), None) == ""
    assert formatar_celula(_coluna(TipoCampo.DATA), "2026-11-01") == "2026-11-01"
    assert formatar_celula(_coluna(TipoCampo.REFERENCIA), 42) == "42"
    for tipo in (TipoCampo.NUMERO, TipoCampo.DATA, TipoCampo.TEXTO, TipoCampo.REFERENCIA):
        assert formatar_celula(_coluna(tipo), None) == ""


def test_localizacao_sai_como_latitude_barra_longitude_com_virgula():
    # arrange
    coluna = _coluna(TipoCampo.LOCALIZACAO)

    # act / assert
    assert (
        formatar_celula(coluna, {"latitude": "-23.550520", "longitude": "-46.633308"})
        == "-23,550520 / -46,633308"
    )
    assert formatar_celula(coluna, None) == ""


def test_foto_sai_como_quantidade():
    # act / assert
    assert formatar_celula(_coluna(TipoCampo.FOTO), [3, 4, 5]) == "3"
    assert formatar_celula(_coluna(TipoCampo.FOTO), None) == ""


# --- injeção de fórmula em planilha (AGENTS.md §12) ---


def test_texto_iniciado_por_caractere_de_formula_e_neutralizado_com_apostrofo():
    # arrange
    coluna = _coluna(TipoCampo.TEXTO)

    # act / assert
    for perigoso in ("=cmd|' /C calc'!A0", "+1+1", "-1+1", "@SOMA(A1)", "\t=1", "\r=1"):
        assert formatar_celula(coluna, perigoso) == "'" + perigoso


def test_texto_comum_nao_e_alterado_e_a_selecao_tambem_e_neutralizada():
    # act / assert
    assert formatar_celula(_coluna(TipoCampo.TEXTO), "Obra A = ok") == "Obra A = ok"
    assert formatar_celula(_coluna(TipoCampo.SELECAO), "=Aprovado") == "'=Aprovado"
    assert formatar_celula(_coluna(TipoCampo.SELECAO), "Aprovado") == "Aprovado"


# --- arquivo CSV ---


def test_csv_tem_bom_utf8_separador_ponto_e_virgula_e_cabecalho_com_unidade():
    # arrange
    colunas = [
        _coluna(TipoCampo.NUMERO, "fck", "fck", unidade="MPa", casas=1),
        _coluna(TipoCampo.TEXTO, "obs", "Observação"),
    ]
    registros = [_registro(1, {"fck": "25.46", "obs": "ok"})]

    # act
    conteudo = gerar_csv(colunas, registros)

    # assert
    assert conteudo.startswith(b"\xef\xbb\xbf")
    assert conteudo.decode("utf-8-sig") == "fck (MPa);Observação\r\n25,5;ok\r\n"


def test_csv_protege_separador_aspas_e_quebra_de_linha_dentro_da_celula():
    # arrange
    colunas = [_coluna(TipoCampo.TEXTO, "obs", "Obs")]
    registros = [_registro(1, {"obs": 'a;b "c"\nlinha 2'})]

    # act
    texto = gerar_csv(colunas, registros).decode("utf-8-sig")

    # assert
    assert texto == 'Obs\r\n"a;b ""c""\nlinha 2"\r\n'


def test_csv_neutraliza_tambem_o_cabecalho_vindo_do_rotulo():
    # arrange
    colunas = [_coluna(TipoCampo.TEXTO, "x", "=HYPERLINK(1)")]

    # act
    texto = gerar_csv(colunas, []).decode("utf-8-sig")

    # assert
    assert texto == "'=HYPERLINK(1)\r\n"


def test_csv_sem_registros_traz_so_o_cabecalho():
    # arrange
    colunas = [
        _coluna(TipoCampo.TEXTO, "a", "A"),
        _coluna(TipoCampo.NUMERO, "b", "B", unidade="kg"),
    ]

    # act / assert
    assert gerar_csv(colunas, []).decode("utf-8-sig") == "A;B (kg)\r\n"


def test_csv_coluna_ausente_no_registro_sai_vazia():
    # arrange: registro de versão antiga que não tinha o campo "b"
    colunas = [_coluna(TipoCampo.TEXTO, "a", "A"), _coluna(TipoCampo.TEXTO, "b", "B")]

    # act
    texto = gerar_csv(colunas, [_registro(1, {"a": "x"})]).decode("utf-8-sig")

    # assert
    assert texto == "A;B\r\nx;\r\n"
