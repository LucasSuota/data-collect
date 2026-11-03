"""Duplicar formulário na API (AGENTS.md §2.10)."""

from fastapi.testclient import TestClient

DEFINICAO = {
    "campos": [
        {"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "casas_decimais": 1},
        {"id": "dobro", "tipo": "calculado", "rotulo": "Dobro", "formula": "umidade * 2"},
    ]
}


def _criar(cliente, nome="ensaio", **extra):
    resposta = cliente.post("/formularios", json={"nome": nome, "definicao": DEFINICAO, **extra})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_duplicar_sem_corpo_devolve_201_no_formato_de_formulario_detalhe(cliente):
    # arrange
    original = _criar(cliente)

    # act
    resposta = cliente.post(f"/formularios/{original['id']}/duplicar")

    # assert
    assert resposta.status_code == 201, resposta.text
    copia = resposta.json()
    assert set(copia) == {"id", "nome", "criado_em", "versao_atual", "pasta_id"}
    assert copia["id"] != original["id"]
    assert copia["nome"] == "ensaio (cópia)"
    assert copia["pasta_id"] is None
    assert copia["versao_atual"]["numero"] == 1
    assert copia["versao_atual"]["formulario_id"] == copia["id"]
    assert copia["versao_atual"]["definicao"] == original["versao_atual"]["definicao"]


def test_duplicar_com_nome_usa_o_nome_informado(cliente):
    # arrange
    original = _criar(cliente)

    # act
    resposta = cliente.post(f"/formularios/{original['id']}/duplicar", json={"nome": "Ensaio B"})

    # assert
    assert resposta.status_code == 201
    assert resposta.json()["nome"] == "Ensaio B"


def test_duplicar_com_nome_nulo_usa_o_padrao(cliente):
    # arrange
    original = _criar(cliente)

    # act
    resposta = cliente.post(f"/formularios/{original['id']}/duplicar", json={"nome": None})

    # assert
    assert resposta.json()["nome"] == "ensaio (cópia)"


def test_duplicar_com_nome_repetido_e_422_no_campo_nome(cliente):
    # arrange
    original = _criar(cliente)

    # act
    resposta = cliente.post(f"/formularios/{original['id']}/duplicar", json={"nome": " ENSAIO "})

    # assert
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert set(corpo) == {"detalhe", "erros"}
    assert [e["campo"] for e in corpo["erros"]] == ["nome"]
    assert len(cliente.get("/formularios").json()) == 1


def test_duplicar_formulario_inexistente_e_404(cliente):
    # act
    resposta = cliente.post("/formularios/99/duplicar")

    # assert
    assert resposta.status_code == 404
    assert set(resposta.json()) == {"detalhe", "erros"}


def test_a_copia_fica_na_pasta_do_original_e_aparece_na_listagem(cliente):
    # arrange
    pasta = cliente.post("/pastas", json={"nome": "Obras"}).json()
    original = _criar(cliente, pasta_id=pasta["id"])

    # act
    copia = cliente.post(f"/formularios/{original['id']}/duplicar").json()

    # assert
    assert copia["pasta_id"] == pasta["id"]
    lista = {f["id"]: f["pasta_id"] for f in cliente.get("/formularios").json()}
    assert lista == {original["id"]: pasta["id"], copia["id"]: pasta["id"]}


def test_o_original_nao_muda_e_a_copia_nao_leva_registros(cliente):
    # arrange
    original = _criar(cliente)
    cliente.post(
        f"/formularios/{original['id']}/registros",
        json={"versao_id": original["versao_atual"]["id"], "dados": {"umidade": "10"}},
    )

    # act
    copia = cliente.post(f"/formularios/{original['id']}/duplicar").json()

    # assert
    assert cliente.get(f"/formularios/{original['id']}").json() == original
    total = cliente.get(f"/formularios/{copia['id']}/registros").json()["total"]
    assert total == 0


def test_duplicar_exige_o_token(app):
    # act
    resposta = TestClient(app).post("/formularios/1/duplicar")

    # assert
    assert resposta.status_code == 401
