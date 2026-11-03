import io
import json
import random
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from forms import servico
from forms.models import DefinicaoInvalida, LoteInvalido, NaoEncontrado
from forms.repositorio import abrir_conexao

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
TEMPLATES = Path(__file__).parent.parent / "templates"


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def corpo(conexao):
    return servico.importar_template(conexao, TEMPLATES / "corpo_de_prova.json", AGORA)


def _registro(conexao, criado, dados):
    return servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, dados, AGORA)


COMPLETO = {"fck_mpa": 25, "diametro_mm": 100, "data_moldagem": "2026-11-01", "carga_kn": 200}


# --- corpo de prova (#24) ---


def test_template_do_corpo_de_prova_publica_sem_erros(conexao):
    # act
    criado = servico.importar_template(conexao, TEMPLATES / "corpo_de_prova.json", AGORA)

    # assert: o nome vem do arquivo
    assert criado.formulario.nome == "corpo_de_prova" and criado.versao.numero == 1
    assert [c.id for c in criado.versao.definicao.campos][-3:] == [
        "ruptura_28d",
        "resistencia_mpa",
        "conforme",
    ]


def test_template_e_a_definicao_do_contrato_e_passa_pela_validacao_sem_erros(conexao):
    # arrange
    definicao = json.loads((TEMPLATES / "corpo_de_prova.json").read_text(encoding="utf-8"))

    # act / assert
    assert servico.validar_definicao(conexao, definicao).valida is True


def test_registro_completo_calcula_resistencia_de_cerca_de_25_46_mpa(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, COMPLETO)

    # assert: 200 kN em 100 mm de diâmetro
    resistencia = Decimal(registro.dados["resistencia_mpa"]["valor"])
    assert resistencia.quantize(Decimal("0.01")) == Decimal("25.46")
    assert abs(resistencia - Decimal("25.4647908947")) < Decimal("0.0000000001")


def test_valor_guardado_mantem_a_precisao_total_e_casas_decimais_so_afeta_exibicao_e_csv(
    conexao, corpo
):
    # arrange
    _registro(conexao, corpo, COMPLETO)

    # act
    guardado = servico.listar_registros(conexao, corpo.formulario.id).itens[0]
    csv = servico.exportar_csv(conexao, corpo.formulario.id).decode("utf-8-sig")

    # assert: o campo tem casas_decimais=1, mas o valor guardado tem 28 dígitos significativos
    texto = guardado.dados["resistencia_mpa"]["valor"]
    assert len(texto.split(".")[1]) > 20
    assert ";25,5;" in csv and "25,46" not in csv  # o CSV arredonda por casas_decimais


def test_formula_da_resistencia_usa_o_valor_completo_e_nao_o_arredondado(conexao, corpo):
    # arrange: a resistência é 25,4648; com fck = 25,47 o ensaio NÃO é conforme,
    # mesmo que o valor exibido, 25,5, fosse maior que 25,47
    dados = COMPLETO | {"fck_mpa": "25.47"}

    # act
    registro = _registro(conexao, corpo, dados)

    # assert
    assert registro.dados["conforme"]["valor"] is False


def test_conforme_verdadeiro_e_falso(conexao, corpo):
    # act
    conforme = _registro(conexao, corpo, COMPLETO | {"fck_mpa": 25})
    nao_conforme = _registro(conexao, corpo, COMPLETO | {"fck_mpa": 30})

    # assert
    assert conforme.dados["conforme"] == {"valor": True, "erro": None}
    assert nao_conforme.dados["conforme"] == {"valor": False, "erro": None}


def test_carga_vazia_deixa_resistencia_e_conforme_vazias_sem_erro(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, {k: v for k, v in COMPLETO.items() if k != "carga_kn"})

    # assert
    assert registro.dados["resistencia_mpa"] == {"valor": None, "erro": None}
    assert registro.dados["conforme"] == {"valor": None, "erro": None}


def test_data_de_ruptura_aos_28_dias(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, COMPLETO | {"data_moldagem": "2026-02-10"})

    # assert: atravessa o fim de fevereiro
    assert registro.dados["ruptura_28d"] == {"valor": "2026-03-10", "erro": None}


def test_diametro_zero_vira_erro_no_campo_e_o_registro_e_salvo(conexao, corpo):
    # act
    registro = _registro(conexao, corpo, COMPLETO | {"diametro_mm": 0})

    # assert
    assert "zero" in registro.dados["resistencia_mpa"]["erro"].lower()
    assert registro.dados["ruptura_28d"]["erro"] is None


def test_campos_obrigatorios_do_template_sao_exigidos(conexao, corpo):
    # act
    with pytest.raises(Exception) as excecao:
        _registro(conexao, corpo, {})

    # assert
    campos = {e.campo for e in excecao.value.erros}
    assert campos == {"fck_mpa", "diametro_mm", "data_moldagem"}


# --- inspeção de obra (#40) ---


def _foto_jpeg() -> bytes:
    gerador = random.Random(3)
    imagem = Image.frombytes("RGB", (200, 150), gerador.randbytes(200 * 150 * 3))
    destino = io.BytesIO()
    imagem.save(destino, "JPEG")
    return destino.getvalue()


def test_template_de_inspecao_publica_e_aceita_um_registro_de_exemplo(conexao, tmp_path):
    # arrange
    criado = servico.importar_template(conexao, TEMPLATES / "inspecao_obra.json", AGORA)
    foto = servico.guardar_anexo(conexao, tmp_path, _foto_jpeg(), AGORA)

    # act
    registro = _registro(
        conexao,
        criado,
        {
            "responsavel": "Ana",
            "data_inspecao": "2026-11-02",
            "local": {"latitude": "-23.550520", "longitude": "-46.633308"},
            "situacao": "Conforme",
            "epi_utilizado": True,
            "area_isolada": True,
            "fotos": [foto.id],
            "observacoes": "tudo certo",
        },
    )

    # assert
    assert registro.dados["seguranca_ok"] == {"valor": True, "erro": None}
    assert registro.dados["local"] == {"latitude": "-23.550520", "longitude": "-46.633308"}
    assert registro.dados["fotos"] == [foto.id]


def test_inspecao_exercita_secao_selecao_sim_nao_localizacao_e_foto(conexao):
    # act
    criado = servico.importar_template(conexao, TEMPLATES / "inspecao_obra.json", AGORA)

    # assert
    tipos = {c.tipo.value for c in criado.versao.definicao.campos}
    assert {"secao", "selecao", "sim_nao", "localizacao", "foto", "calculado"} <= tipos


def test_inspecao_seguranca_depende_dos_dois_sim_nao(conexao):
    # arrange
    criado = servico.importar_template(conexao, TEMPLATES / "inspecao_obra.json", AGORA)
    base = {"responsavel": "Ana", "data_inspecao": "2026-11-02", "situacao": "Pendente"}

    # act
    so_epi = _registro(conexao, criado, base | {"epi_utilizado": True, "area_isolada": False})
    sem_resposta = _registro(conexao, criado, base | {"epi_utilizado": True})

    # assert
    assert so_epi.dados["seguranca_ok"]["valor"] is False
    assert sem_resposta.dados["seguranca_ok"]["valor"] is None


def test_inspecao_recusa_situacao_fora_das_opcoes(conexao):
    # arrange
    criado = servico.importar_template(conexao, TEMPLATES / "inspecao_obra.json", AGORA)

    # act
    with pytest.raises(Exception) as excecao:
        _registro(
            conexao,
            criado,
            {"responsavel": "A", "data_inspecao": "2026-11-02", "situacao": "Talvez"},
        )

    # assert
    assert [e.campo for e in excecao.value.erros] == ["situacao"]


def test_os_dois_templates_convivem_no_mesmo_banco(conexao):
    # act
    criados = servico.importar_templates(
        conexao, [TEMPLATES / "inspecao_obra.json", TEMPLATES / "corpo_de_prova.json"], AGORA
    )

    # assert
    assert sorted(c.formulario.nome for c in criados) == ["corpo_de_prova", "inspecao_obra"]


# --- importação ---


def test_importar_com_nome_explicito_ignora_o_nome_do_arquivo(conexao):
    # act
    criado = servico.importar_template(
        conexao, TEMPLATES / "corpo_de_prova.json", AGORA, nome="Corpo 2"
    )

    # assert
    assert criado.formulario.nome == "Corpo 2"


def test_importar_duas_vezes_o_mesmo_template_e_nome_repetido(conexao, corpo):
    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.importar_template(conexao, TEMPLATES / "corpo_de_prova.json", AGORA)

    # assert
    assert [e.campo for e in excecao.value.erros] == ["nome"]


def test_template_inexistente_e_nao_encontrado(conexao, tmp_path):
    # act / assert
    with pytest.raises(NaoEncontrado, match="nao_existe.json"):
        servico.importar_template(conexao, tmp_path / "nao_existe.json", AGORA)


def test_template_que_nao_e_json_gera_erro_claro_e_nao_cria_nada(conexao, tmp_path):
    # arrange
    arquivo = tmp_path / "quebrado.json"
    arquivo.write_text('{"campos": [', encoding="utf-8")

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.importar_template(conexao, arquivo, AGORA)

    # assert
    assert excecao.value.erros[0].campo == "arquivo" and "JSON" in excecao.value.erros[0].mensagem
    assert servico.listar_formularios(conexao) == []


def test_template_com_definicao_invalida_nao_cria_nada(conexao, tmp_path):
    # arrange
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text(json.dumps({"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}))

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.importar_template(conexao, arquivo, AGORA)

    # assert
    assert excecao.value.erros[0].campo == "a.tipo"
    assert servico.listar_formularios(conexao) == []


def test_templates_dependentes_importam_em_qualquer_ordem_pelo_lote(conexao, tmp_path):
    # arrange: o nome do arquivo é o nome do formulário, que é como a referência o encontra
    (tmp_path / "ensaio.json").write_text(
        json.dumps(
            {"campos": [{"id": "umidade", "tipo": "numero", "rotulo": "U", "compartilhado": True}]}
        )
    )
    (tmp_path / "proctor.json").write_text(
        json.dumps(
            {
                "campos": [
                    {"id": "ensaio", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
                    {
                        "id": "dobro",
                        "tipo": "calculado",
                        "rotulo": "D",
                        "formula": "ensaio__umidade * 2",
                    },
                ]
            }
        )
    )

    # act: o dependente vem primeiro na lista
    criados = servico.importar_templates(
        conexao, [tmp_path / "proctor.json", tmp_path / "ensaio.json"], AGORA
    )

    # assert
    assert [c.formulario.nome for c in criados] == ["ensaio", "proctor"]


def test_importar_um_template_dependente_sem_a_origem_falha_com_erro_claro(conexao, tmp_path):
    # arrange
    (tmp_path / "proctor.json").write_text(
        json.dumps(
            {
                "campos": [
                    {"id": "ensaio", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"}
                ]
            }
        )
    )

    # act
    with pytest.raises(DefinicaoInvalida) as excecao:
        servico.importar_template(conexao, tmp_path / "proctor.json", AGORA)

    # assert
    assert excecao.value.erros[0].campo == "ensaio.formulario"


def test_lote_de_templates_com_um_invalido_nao_cria_nenhum(conexao, tmp_path):
    # arrange
    (tmp_path / "ruim.json").write_text(json.dumps({"campos": "x"}))

    # act
    with pytest.raises(LoteInvalido):
        servico.importar_templates(
            conexao, [TEMPLATES / "corpo_de_prova.json", tmp_path / "ruim.json"], AGORA
        )

    # assert
    assert servico.listar_formularios(conexao) == []


# --- cadeia geotécnica: umidade → Proctor → densidade in situ ---

AMOSTRA = {"identificacao": "P-01", "data_ensaio": "2026-11-02"}

CADEIA = [
    TEMPLATES / "densidade_insitu.json",
    TEMPLATES / "proctor.json",
    TEMPLATES / "ensaio_umidade.json",
]


@pytest.fixture
def cadeia(conexao):
    # a ordem do argumento é de propósito invertida: a origem é criada primeiro de qualquer jeito
    criados = servico.importar_templates(conexao, CADEIA, AGORA)
    return {c.formulario.nome: c for c in criados}


def _valor(registro, campo):
    guardado = registro.dados[campo]
    return Decimal(guardado["valor"] if isinstance(guardado, dict) else guardado)


def test_a_cadeia_de_templates_importa_junta_mesmo_fora_de_ordem(cadeia):
    # assert
    assert sorted(cadeia) == ["densidade_insitu", "ensaio_umidade", "proctor"]


def test_teor_de_umidade_e_a_perda_de_agua_sobre_a_massa_de_solo_seco(conexao, cadeia):
    # arrange: cápsula 20 g, úmido 120 g, seco 100 g → (120 - 100) / (100 - 20) = 25 %
    umidade = cadeia["ensaio_umidade"]

    # act
    registro = _registro(
        conexao, umidade, {**AMOSTRA, "tara_g": 20, "massa_umida_g": 120, "massa_seca_g": 100}
    )

    # assert
    assert _valor(registro, "umidade_pct") == Decimal("25")


def test_grau_de_compactacao_usa_o_proctor_e_a_umidade_de_campo(conexao, cadeia):
    # arrange
    ensaio = _registro(
        conexao,
        cadeia["ensaio_umidade"],
        {**AMOSTRA, "tara_g": 20, "massa_umida_g": 120, "massa_seca_g": 100},
    )
    proctor = _registro(
        conexao,
        cadeia["proctor"],
        {
            "ensaio_umidade": ensaio.id,
            "energia": "Normal",
            "umidade_otima_pct": 12,
            "gamad_max": "1.85",
        },
    )

    # act: γd campo = 1800 / 1000 / (1 + 25/100) = 1,44 g/cm³ → GC = 1,44 / 1,85 = 77,8 %
    insitu = _registro(
        conexao,
        cadeia["densidade_insitu"],
        {
            "proctor": proctor.id,
            "ensaio_umidade_campo": ensaio.id,
            "massa_solo_g": 1800,
            "volume_cm3": 1000,
            "gc_minimo_pct": 95,
        },
    )

    # assert
    assert _valor(proctor, "desvio_umidade") == Decimal("13")
    assert _valor(insitu, "gamad_campo") == Decimal("1.44")
    assert round(_valor(insitu, "gc_pct"), 1) == Decimal("77.8")
    assert insitu.dados["conforme"]["valor"] is False


def test_compactacao_acima_do_minimo_e_conforme(conexao, cadeia):
    # arrange: umidade de 10 % e Proctor de 1,50 → γd campo = 1,70 / 1,10 ≈ 1,545 → GC ≈ 103 %
    ensaio = _registro(
        conexao,
        cadeia["ensaio_umidade"],
        {**AMOSTRA, "tara_g": 0, "massa_umida_g": 110, "massa_seca_g": 100},
    )
    proctor = _registro(
        conexao,
        cadeia["proctor"],
        {
            "ensaio_umidade": ensaio.id,
            "energia": "Normal",
            "umidade_otima_pct": 10,
            "gamad_max": "1.50",
        },
    )

    # act
    insitu = _registro(
        conexao,
        cadeia["densidade_insitu"],
        {
            "proctor": proctor.id,
            "ensaio_umidade_campo": ensaio.id,
            "massa_solo_g": 1700,
            "volume_cm3": 1000,
            "gc_minimo_pct": 95,
        },
    )

    # assert
    assert insitu.dados["conforme"]["valor"] is True


def test_corrigir_o_ensaio_de_umidade_recalcula_toda_a_cadeia(conexao, cadeia, tmp_path):
    # arrange
    base = {**AMOSTRA, "tara_g": 0, "massa_umida_g": 110, "massa_seca_g": 100}
    ensaio = _registro(conexao, cadeia["ensaio_umidade"], base)
    proctor = _registro(
        conexao,
        cadeia["proctor"],
        {
            "ensaio_umidade": ensaio.id,
            "energia": "Normal",
            "umidade_otima_pct": 10,
            "gamad_max": "1.50",
        },
    )
    insitu = _registro(
        conexao,
        cadeia["densidade_insitu"],
        {
            "proctor": proctor.id,
            "ensaio_umidade_campo": ensaio.id,
            "massa_solo_g": 1700,
            "volume_cm3": 1000,
            "gc_minimo_pct": 95,
        },
    )

    # act: a umidade sobe para 30 %, e o γd de campo cai
    servico.atualizar_registro(conexao, ensaio.id, {**base, "massa_umida_g": 130}, AGORA, tmp_path)

    # assert
    depois = servico.obter_registro(conexao, insitu.id)
    assert _valor(depois, "gamad_campo") < _valor(insitu, "gamad_campo")
    assert depois.dados["conforme"]["valor"] is False
