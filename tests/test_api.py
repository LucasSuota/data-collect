import pytest
from fastapi.testclient import TestClient

CORPO = {
    "campos": [
        {"id": "fck_mpa", "tipo": "numero", "rotulo": "fck", "unidade": "MPa", "obrigatorio": True},
        {"id": "diametro_mm", "tipo": "numero", "rotulo": "Diâmetro", "unidade": "mm"},
        {"id": "data_moldagem", "tipo": "data", "rotulo": "Data de moldagem"},
        {"id": "carga_kn", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
        {"id": "obs", "tipo": "texto", "rotulo": "Observação"},
        {
            "id": "ruptura",
            "tipo": "calculado",
            "rotulo": "Ruptura",
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
ENTRADA = {"fck_mpa": 25, "diametro_mm": "100", "data_moldagem": "2026-11-01", "carga_kn": 200}


def _criar(cliente: TestClient, nome="corpo", definicao=CORPO):
    resposta = cliente.post("/formularios", json={"nome": nome, "definicao": definicao})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _registro(cliente: TestClient, formulario, dados=ENTRADA):
    versao_id = formulario["versao_atual"]["id"]
    return cliente.post(
        f"/formularios/{formulario['id']}/registros", json={"versao_id": versao_id, "dados": dados}
    )


# --- formulários e versões ---


def test_criar_formulario_devolve_201_com_a_versao_1_completa(cliente):
    # act
    resposta = cliente.post("/formularios", json={"nome": "corpo", "definicao": CORPO})

    # assert
    corpo = resposta.json()
    assert resposta.status_code == 201
    assert corpo["nome"] == "corpo" and corpo["versao_atual"]["numero"] == 1
    assert corpo["versao_atual"]["definicao"]["campos"][0]["id"] == "fck_mpa"
    assert corpo["criado_em"] == "2026-11-02T10:00:00+00:00"


def test_definicao_invalida_devolve_422_com_todos_os_erros_localizados_e_nao_cria_nada(cliente):
    # arrange
    ruim = {
        "campos": [
            {"id": "pi", "tipo": "texto", "rotulo": "A"},
            {"id": "b", "tipo": "x", "rotulo": "B"},
        ]
    }

    # act
    resposta = cliente.post("/formularios", json={"nome": "ruim", "definicao": ruim})

    # assert
    corpo = resposta.json()
    assert resposta.status_code == 422 and corpo["detalhe"] == "Definição inválida."
    assert {e["campo"] for e in corpo["erros"]} == {"campos[0].id", "b.tipo"}
    assert cliente.get("/formularios").json() == []


def test_erro_de_formula_traz_a_posicao_para_o_front_sublinhar(cliente):
    # arrange
    definicao = {
        "campos": [
            {"id": "n", "tipo": "numero", "rotulo": "N"},
            {"id": "c", "tipo": "calculado", "rotulo": "C", "formula": "n + __import__('os')"},
        ]
    }

    # act
    resposta = cliente.post("/formularios", json={"nome": "f", "definicao": definicao})

    # assert
    assert resposta.json()["erros"][0] == {
        "campo": "c.formula",
        "mensagem": resposta.json()["erros"][0]["mensagem"],
        "posicao": {"inicio": 4, "fim": 20},
    }


def test_nome_repetido_e_422_no_campo_nome(cliente):
    # arrange
    _criar(cliente, "corpo")

    # act
    resposta = cliente.post("/formularios", json={"nome": "  CORPO ", "definicao": CORPO})

    # assert
    assert resposta.status_code == 422
    assert [e["campo"] for e in resposta.json()["erros"]] == ["nome"]


def test_listar_formularios_traz_a_versao_atual_sem_definicoes(cliente):
    # arrange
    criado = _criar(cliente)
    cliente.post(f"/formularios/{criado['id']}/versoes", json={"definicao": CORPO})

    # act
    lista = cliente.get("/formularios").json()

    # assert
    assert lista == [
        {
            "id": criado["id"],
            "nome": "corpo",
            "criado_em": "2026-11-02T10:00:00+00:00",
            "versao_atual_id": lista[0]["versao_atual_id"],
            "versao_atual_numero": 2,
            "pasta_id": None,
        }
    ]


def test_obter_formulario_traz_a_versao_atual_completa(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    detalhe = cliente.get(f"/formularios/{criado['id']}").json()

    # assert
    assert detalhe == criado


def test_formulario_inexistente_e_404_uniforme(cliente):
    # act
    resposta = cliente.get("/formularios/999")

    # assert
    assert resposta.status_code == 404 and resposta.json() == {
        "detalhe": "Formulário 999 não encontrado.",
        "erros": [],
    }


def test_publicar_versao_devolve_201_numero_seguinte_e_a_primeira_nao_muda(cliente):
    # arrange
    criado = _criar(cliente)
    nova = {"campos": CORPO["campos"][:1]}

    # act
    resposta = cliente.post(f"/formularios/{criado['id']}/versoes", json={"definicao": nova})
    primeira = cliente.get(f"/formularios/{criado['id']}/versoes/{criado['versao_atual']['id']}")

    # assert
    assert resposta.status_code == 201 and resposta.json()["numero"] == 2
    assert len(primeira.json()["definicao"]["campos"]) == len(CORPO["campos"])
    versoes = cliente.get(f"/formularios/{criado['id']}/versoes").json()
    assert [v["numero"] for v in versoes] == [1, 2] and "definicao" not in versoes[0]


def test_versao_invalida_e_422_e_nao_publica(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = cliente.post(
        f"/formularios/{criado['id']}/versoes", json={"definicao": {"campos": "x"}}
    )

    # assert
    assert resposta.status_code == 422
    assert len(cliente.get(f"/formularios/{criado['id']}/versoes").json()) == 1


def test_versao_de_outro_formulario_e_404(cliente):
    # arrange
    a, b = _criar(cliente, "a"), _criar(cliente, "b")

    # act / assert
    assert (
        cliente.get(f"/formularios/{b['id']}/versoes/{a['versao_atual']['id']}").status_code == 404
    )


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_nao_existe_alterar_nem_apagar_versao(cliente, metodo):
    # arrange
    criado = _criar(cliente)
    caminho = f"/formularios/{criado['id']}/versoes/{criado['versao_atual']['id']}"

    # act / assert
    assert getattr(cliente, metodo)(caminho).status_code == 405


def test_excluir_formulario_livre_devolve_204(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = cliente.delete(f"/formularios/{criado['id']}")

    # assert
    assert resposta.status_code == 204 and resposta.content == b""
    assert cliente.get(f"/formularios/{criado['id']}").status_code == 404


def test_excluir_formulario_com_registros_e_409_uniforme(cliente):
    # arrange
    criado = _criar(cliente)
    _registro(cliente, criado)

    # act
    resposta = cliente.delete(f"/formularios/{criado['id']}")

    # assert
    assert resposta.status_code == 409 and "registro" in resposta.json()["detalhe"]
    assert resposta.json()["erros"] == []


def test_excluir_formulario_com_dependente_e_409(cliente):
    # arrange
    origem = _criar(
        cliente,
        "ensaio",
        {"campos": [{"id": "u", "tipo": "numero", "rotulo": "U", "compartilhado": True}]},
    )
    _criar(
        cliente,
        "proctor",
        {"campos": [{"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"}]},
    )

    # act
    resposta = cliente.delete(f"/formularios/{origem['id']}")

    # assert
    assert resposta.status_code == 409 and "proctor" in resposta.json()["detalhe"]


# --- lote (#59) ---

ENSAIO = {"campos": [{"id": "umidade", "tipo": "numero", "rotulo": "U", "compartilhado": True}]}
PROCTOR = {
    "campos": [
        {"id": "ensaio", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
        {
            "id": "seca",
            "tipo": "calculado",
            "rotulo": "S",
            "formula": "ensaio__umidade * 2",
            "compartilhado": True,
        },
    ]
}
INSITU = {
    "campos": [
        {"id": "proctor", "tipo": "referencia", "rotulo": "P", "formulario": "proctor"},
        {"id": "grau", "tipo": "calculado", "rotulo": "G", "formula": "proctor__seca + 1"},
    ]
}


def test_lote_valido_de_tres_formularios_na_ordem_de_criacao(cliente):
    # arrange: enviado embaralhado
    corpo = {
        "formularios": [
            {"nome": "insitu", "definicao": INSITU},
            {"nome": "ensaio", "definicao": ENSAIO},
            {"nome": "proctor", "definicao": PROCTOR},
        ]
    }

    # act
    resposta = cliente.post("/formularios/lote", json=corpo)

    # assert
    assert resposta.status_code == 201
    assert [f["nome"] for f in resposta.json()] == ["ensaio", "proctor", "insitu"]
    assert all(f["versao_atual_numero"] == 1 for f in resposta.json())
    assert len(cliente.get("/formularios").json()) == 3


def test_lote_com_erro_em_um_formulario_nao_cria_nenhum_e_prefixa_o_campo_com_o_nome(cliente):
    # arrange
    insitu_ruim = {
        "campos": [
            {"id": "proctor", "tipo": "referencia", "rotulo": "P", "formulario": "proctor"},
            {"id": "grau", "tipo": "calculado", "rotulo": "G", "formula": "proctor__inexistente"},
        ]
    }
    corpo = {
        "formularios": [
            {"nome": "ensaio", "definicao": ENSAIO},
            {"nome": "proctor", "definicao": PROCTOR},
            {"nome": "insitu", "definicao": insitu_ruim},
        ]
    }

    # act
    resposta = cliente.post("/formularios/lote", json=corpo)

    # assert
    assert resposta.status_code == 422
    assert [e["campo"] for e in resposta.json()["erros"]] == ["insitu.grau.formula"]
    assert cliente.get("/formularios").json() == []


def test_lote_pode_referenciar_formulario_ja_existente(cliente):
    # arrange
    _criar(cliente, "ensaio", ENSAIO)

    # act
    resposta = cliente.post(
        "/formularios/lote", json={"formularios": [{"nome": "proctor", "definicao": PROCTOR}]}
    )

    # assert
    assert resposta.status_code == 201


def test_lote_com_nome_repetido_e_422(cliente):
    # act
    resposta = cliente.post(
        "/formularios/lote",
        json={
            "formularios": [
                {"nome": "a", "definicao": ENSAIO},
                {"nome": "A", "definicao": ENSAIO},
            ]
        },
    )

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "A.nome"


# --- validar, prévia, catálogo ---


def test_validar_definicao_incompleta_responde_200_com_todos_os_erros(cliente):
    # act
    resposta = cliente.post(
        "/definicoes/validar",
        json={"definicao": {"campos": [{"id": "a", "tipo": "x", "rotulo": ""}, {}]}},
    )

    # assert
    corpo = resposta.json()
    assert resposta.status_code == 200 and corpo["valida"] is False
    assert {e["campo"] for e in corpo["erros"]} >= {"a.tipo", "a.rotulo", "campos[1].id"}
    assert set(corpo) == {"valida", "erros"}  # não segue o formato {detalhe, erros}


def test_validar_definicao_valida_e_definicao_que_nem_e_objeto(cliente):
    # act / assert
    assert cliente.post("/definicoes/validar", json={"definicao": CORPO}).json() == {
        "valida": True,
        "erros": [],
    }
    nula = cliente.post("/definicoes/validar", json={"definicao": None})
    assert nula.status_code == 200 and nula.json()["erros"][0]["campo"] == "campos"


def test_validar_nao_salva_nada(cliente):
    # act
    cliente.post("/definicoes/validar", json={"definicao": CORPO})

    # assert
    assert cliente.get("/formularios").json() == []


def test_previa_calcula_sem_salvar_e_coincide_com_o_calculo_do_salvar(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    previa = cliente.post(
        "/definicoes/previa", json={"definicao": CORPO, "valores": ENTRADA}
    ).json()
    salvo = _registro(cliente, criado).json()

    # assert
    assert previa["valida"] is True and previa["erros"] == []
    for id_do_campo, resultado in previa["calculados"].items():
        assert salvo["dados"][id_do_campo] == resultado
    assert previa["calculados"]["conforme"] == {"valor": True, "erro": None}


def test_previa_de_definicao_invalida_devolve_a_mesma_lista_do_validar(cliente):
    # arrange
    ruim = {"campos": [{"id": "a", "tipo": "x", "rotulo": "A"}]}

    # act
    previa = cliente.post("/definicoes/previa", json={"definicao": ruim, "valores": {}}).json()
    validar = cliente.post("/definicoes/validar", json={"definicao": ruim}).json()

    # assert
    assert (
        previa["valida"] is False
        and previa["erros"] == validar["erros"]
        and previa["calculados"] == {}
    )


def test_previa_sem_valores_usa_o_padrao_vazio(cliente):
    # act
    previa = cliente.post("/definicoes/previa", json={"definicao": CORPO}).json()

    # assert
    assert previa["calculados"]["resistencia_mpa"] == {"valor": None, "erro": None}


def test_catalogo_traz_tipos_funcoes_pi_e_nomes_reservados(cliente):
    # act
    catalogo = cliente.get("/catalogo").json()

    # assert
    assert {t["id"] for t in catalogo["tipos"]} >= {"numero", "calculado", "localizacao"}
    assert {f["nome"] for f in catalogo["funcoes"]} == {"se", "min", "max", "media", "soma", "dias"}
    assert [c["nome"] for c in catalogo["constantes"]] == ["pi"]
    assert "pi" in catalogo["nomes_reservados"] and "dias" in catalogo["nomes_reservados"]


# --- registros ---


def test_criar_registro_devolve_201_com_numeros_como_string_e_calculados_em_valor_erro(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = _registro(cliente, criado, ENTRADA | {"fck_mpa": 25.5})

    # assert
    corpo = resposta.json()
    assert resposta.status_code == 201
    assert corpo["dados"]["fck_mpa"] == "25.5" and corpo["dados"]["diametro_mm"] == "100"
    assert corpo["dados"]["ruptura"] == {"valor": "2026-11-29", "erro": None}
    assert corpo["dados"]["resistencia_mpa"]["valor"].startswith("25.4647908947")
    assert (
        corpo["versao_id"] == criado["versao_atual"]["id"]
        and corpo["formulario_id"] == criado["id"]
    )


def test_registro_exige_versao_id(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = cliente.post(f"/formularios/{criado['id']}/registros", json={"dados": ENTRADA})

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "versao_id"


def test_versao_inexistente_no_registro_e_404(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = cliente.post(
        f"/formularios/{criado['id']}/registros", json={"versao_id": 999, "dados": ENTRADA}
    )

    # assert
    assert resposta.status_code == 404


def test_chave_de_campo_calculado_e_inexistente_e_422_indicando_o_campo(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = _registro(cliente, criado, ENTRADA | {"conforme": True, "fantasma": 1})

    # assert
    assert resposta.status_code == 422 and resposta.json()["detalhe"] == "Registro inválido."
    assert {e["campo"] for e in resposta.json()["erros"]} == {"conforme", "fantasma"}


def test_422_lista_os_erros_por_id(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = _registro(cliente, criado, {"diametro_mm": "abc", "data_moldagem": "01/11/2026"})

    # assert
    assert {e["campo"] for e in resposta.json()["erros"]} == {
        "fck_mpa",
        "diametro_mm",
        "data_moldagem",
    }


def test_erro_de_calculo_nunca_bloqueia_o_registro_e_o_erro_esta_no_campo(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = _registro(cliente, criado, ENTRADA | {"diametro_mm": 0})

    # assert
    assert resposta.status_code == 201
    assert "zero" in resposta.json()["dados"]["resistencia_mpa"]["erro"].lower()


def test_obter_e_atualizar_registro_substitui_tudo_e_mantem_a_versao(cliente):
    # arrange
    criado = _criar(cliente)
    registro = _registro(cliente, criado).json()

    # act
    atualizado = cliente.put(
        f"/registros/{registro['id']}",
        json={"dados": {"fck_mpa": 30}, "revisao": registro["revisao"]},
    )
    lido = cliente.get(f"/registros/{registro['id']}")

    # assert
    assert atualizado.status_code == 200 and lido.json() == atualizado.json()
    assert (
        atualizado.json()["dados"]["fck_mpa"] == "30"
        and atualizado.json()["dados"]["diametro_mm"] is None
    )
    assert atualizado.json()["versao_id"] == registro["versao_id"]
    assert set(lido.json()) == {
        "id",
        "formulario_id",
        "versao_id",
        "dados",
        "revisao",
        "criado_por",
        "atualizado_por",
        "criado_em",
        "atualizado_em",
        "estado",
    }


def test_nao_existe_patch_de_registro(cliente):
    # act / assert
    assert cliente.patch("/registros/1", json={"dados": {}}).status_code == 405


def test_atualizar_ou_obter_registro_inexistente_e_404(cliente):
    # act / assert
    assert cliente.get("/registros/999").status_code == 404
    assert cliente.put("/registros/999", json={"dados": {}, "revisao": 1}).status_code == 404
    assert cliente.delete("/registros/999").status_code == 404


def test_excluir_registro_devolve_204_e_apaga_de_verdade(cliente):
    # arrange
    registro = _registro(cliente, _criar(cliente)).json()

    # act
    resposta = cliente.delete(f"/registros/{registro['id']}")

    # assert
    assert (
        resposta.status_code == 204
        and cliente.get(f"/registros/{registro['id']}").status_code == 404
    )


def test_excluir_registro_referenciado_e_409_e_depois_de_liberado_e_204(cliente):
    # arrange
    ensaio = _criar(cliente, "ensaio", ENSAIO)
    proctor = _criar(cliente, "proctor", PROCTOR)
    origem = cliente.post(
        f"/formularios/{ensaio['id']}/registros",
        json={"versao_id": ensaio["versao_atual"]["id"], "dados": {"umidade": "0.5"}},
    ).json()
    dependente = cliente.post(
        f"/formularios/{proctor['id']}/registros",
        json={"versao_id": proctor["versao_atual"]["id"], "dados": {"ensaio": origem["id"]}},
    ).json()

    # act
    bloqueado = cliente.delete(f"/registros/{origem['id']}")
    cliente.delete(f"/registros/{dependente['id']}")
    liberado = cliente.delete(f"/registros/{origem['id']}")

    # assert
    assert bloqueado.status_code == 409 and liberado.status_code == 204


def test_atualizar_a_origem_recalcula_o_dependente_na_resposta_seguinte(cliente):
    # arrange
    ensaio = _criar(cliente, "ensaio", ENSAIO)
    proctor = _criar(cliente, "proctor", PROCTOR)
    origem = cliente.post(
        f"/formularios/{ensaio['id']}/registros",
        json={"versao_id": ensaio["versao_atual"]["id"], "dados": {"umidade": "0.5"}},
    ).json()
    dependente = cliente.post(
        f"/formularios/{proctor['id']}/registros",
        json={"versao_id": proctor["versao_atual"]["id"], "dados": {"ensaio": origem["id"]}},
    ).json()
    assert dependente["dados"]["seca"]["valor"] == "1.0"

    # act
    cliente.put(
        f"/registros/{origem['id']}", json={"dados": {"umidade": "2"}, "revisao": origem["revisao"]}
    )

    # assert
    assert cliente.get(f"/registros/{dependente['id']}").json()["dados"]["seca"]["valor"] == "4"


# --- listagem e CSV ---


def test_listagem_com_paginacao_total_e_versao(cliente):
    # arrange
    criado = _criar(cliente)
    for _ in range(3):
        _registro(cliente, criado)

    # act
    pagina = cliente.get(
        f"/formularios/{criado['id']}/registros", params={"limite": 2, "deslocamento": 2}
    ).json()

    # assert
    assert pagina["total"] == 3 and len(pagina["itens"]) == 1
    assert pagina["versao_id"] == criado["versao_atual"]["id"]
    assert set(pagina) == {"versao_id", "colunas", "itens", "total", "exibicao"}


def test_filtro_por_campo_usa_filtro_campo_valor_repetivel(cliente):
    # arrange
    criado = _criar(cliente)
    _registro(cliente, criado, ENTRADA | {"obs": "alfa"})
    _registro(cliente, criado, ENTRADA | {"obs": "beta", "fck_mpa": 40})

    # act
    por_texto = cliente.get(
        f"/formularios/{criado['id']}/registros", params={"filtro": "obs:beta"}
    ).json()
    por_calculado = cliente.get(
        f"/formularios/{criado['id']}/registros", params=[("filtro", "conforme:true")]
    ).json()
    combinado = cliente.get(
        f"/formularios/{criado['id']}/registros",
        params=[("filtro", "obs:alfa"), ("filtro", "conforme:true")],
    ).json()

    # assert
    assert por_texto["total"] == 1 and por_calculado["total"] == 1 and combinado["total"] == 1


@pytest.mark.parametrize(
    "filtro", ["fck_mpa:25", "fantasma:x", "semdoispontos", ":x", "a') OR 1=1 --:x"]
)
def test_filtro_em_campo_nao_filtravel_ou_mal_formado_e_422(cliente, filtro):
    # arrange
    criado = _criar(cliente)

    # act
    resposta = cliente.get(f"/formularios/{criado['id']}/registros", params={"filtro": filtro})

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"]


def test_filtro_por_data_de_criacao(cliente):
    # arrange
    criado = _criar(cliente)
    _registro(cliente, criado)

    # act
    dentro = cliente.get(
        f"/formularios/{criado['id']}/registros",
        params={"criado_de": "2026-11-02", "criado_ate": "2026-11-02"},
    ).json()
    fora = cliente.get(
        f"/formularios/{criado['id']}/registros", params={"criado_de": "2026-11-03"}
    ).json()
    invalida = cliente.get(
        f"/formularios/{criado['id']}/registros", params={"criado_de": "02/11/2026"}
    )

    # assert
    assert dentro["total"] == 1 and fora["total"] == 0 and invalida.status_code == 422


def test_listar_versao_antiga_depois_da_v2(cliente):
    # arrange
    criado = _criar(cliente)
    _registro(cliente, criado)
    cliente.post(f"/formularios/{criado['id']}/versoes", json={"definicao": {"campos": []}})

    # act
    atual = cliente.get(f"/formularios/{criado['id']}/registros").json()
    antiga = cliente.get(
        f"/formularios/{criado['id']}/registros", params={"versao_id": criado["versao_atual"]["id"]}
    ).json()

    # assert
    assert atual["total"] == 0 and antiga["total"] == 1


def test_exportar_csv_abre_no_excel_em_portugues(cliente):
    # arrange
    criado = _criar(cliente, "Corpo de prova")
    _registro(cliente, criado, ENTRADA | {"obs": "=cmd|' /C calc'!A0"})

    # act
    resposta = cliente.get(f"/formularios/{criado['id']}/registros/exportar")

    # assert
    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "text/csv; charset=utf-8"
    assert resposta.headers["content-disposition"] == 'attachment; filename="Corpo_de_prova.csv"'
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    texto = resposta.content.decode("utf-8-sig")
    assert texto.split("\r\n")[0].startswith("fck (MPa);Diâmetro (mm);")
    assert ";25,5;" in texto and "'=cmd|' /C calc'!A0" in texto


def test_exportar_usa_os_mesmos_filtros_da_listagem_e_recusa_os_invalidos(cliente):
    # arrange
    criado = _criar(cliente)
    _registro(cliente, criado, ENTRADA | {"obs": "alfa"})

    # act
    vazio = cliente.get(
        f"/formularios/{criado['id']}/registros/exportar", params={"filtro": "obs:beta"}
    )
    invalido = cliente.get(
        f"/formularios/{criado['id']}/registros/exportar", params={"filtro": "fck_mpa:1"}
    )

    # assert
    assert vazio.content.decode("utf-8-sig").count("\r\n") == 1
    assert invalido.status_code == 422


def test_nome_do_arquivo_do_csv_nunca_leva_caracteres_perigosos(cliente):
    # arrange
    criado = _criar(cliente, 'x"; filename=../../etc/passwd')

    # act
    resposta = cliente.get(f"/formularios/{criado['id']}/registros/exportar")

    # assert: aspas, ponto e vírgula, barras e pontos viram "_"; nada escapa do atributo
    assert (
        resposta.headers["content-disposition"]
        == 'attachment; filename="x_filename_etc_passwd.csv"'
    )


def test_exportar_formulario_inexistente_e_404(cliente):
    # act / assert
    assert cliente.get("/formularios/999/registros/exportar").status_code == 404


def test_definicao_volta_como_foi_escrita_sem_campos_nulos_inventados(cliente):
    # arrange
    criado = _criar(cliente)

    # act
    campos = cliente.get(f"/formularios/{criado['id']}").json()["versao_atual"]["definicao"][
        "campos"
    ]

    # assert: o campo simples não ganha `unidade: null`, `opcoes: null`...
    obs = next(c for c in campos if c["id"] == "obs")
    assert obs == {"id": "obs", "tipo": "texto", "rotulo": "Observação"}
    assert campos == CORPO["campos"]


def test_listagem_traz_as_colunas_com_o_que_o_front_precisa_para_exibir_e_filtrar(cliente):
    # arrange
    definicao = {
        "campos": [
            {"id": "sec", "tipo": "secao", "rotulo": "S"},
            {"id": "fase", "tipo": "selecao", "rotulo": "Fase", "opcoes": ["A", "B"]},
            {"id": "n", "tipo": "numero", "rotulo": "N", "unidade": "kg", "casas_decimais": 2},
            {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "n * 2"},
            {"id": "alto", "tipo": "calculado", "rotulo": "Alto?", "formula": "n > 10"},
            {"id": "dia", "tipo": "calculado", "rotulo": "Dia", "formula": "d + dias(1)"},
            {"id": "d", "tipo": "data", "rotulo": "D"},
        ]
    }
    criado = _criar(cliente, "f", definicao)

    # act
    colunas = cliente.get(f"/formularios/{criado['id']}/registros").json()["colunas"]
    por_id = {c["id"]: c for c in colunas}

    # assert: sem a seção; o calculado diz o tipo do resultado; só os tipos aceitos são filtráveis
    assert [c["id"] for c in colunas] == ["fase", "n", "dobro", "alto", "dia", "d"]
    assert por_id["fase"] == {
        "id": "fase",
        "rotulo": "Fase",
        "unidade": None,
        "tipo": "selecao",
        "casas_decimais": None,
        "resultado": None,
        "opcoes": ["A", "B"],
        "filtravel": True,
    }
    assert (por_id["n"]["unidade"], por_id["n"]["casas_decimais"], por_id["n"]["filtravel"]) == (
        "kg",
        2,
        False,
    )
    assert [por_id[i]["resultado"] for i in ("dobro", "alto", "dia")] == [
        "numero",
        "booleano",
        "data",
    ]
    assert [por_id[i]["filtravel"] for i in ("dobro", "alto", "dia", "d")] == [
        False,
        True,
        False,
        False,
    ]
