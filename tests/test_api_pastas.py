"""Pastas e subpastas na API (AGENTS.md §2.10)."""

from fastapi.testclient import TestClient

DEFINICAO = {"campos": [{"id": "obs", "tipo": "texto", "rotulo": "Observação"}]}
CRIADO_EM = "2026-11-02T10:00:00+00:00"


def _pasta(cliente, nome="Obras", pasta_pai_id=None):
    resposta = cliente.post("/pastas", json={"nome": nome, "pasta_pai_id": pasta_pai_id})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _formulario(cliente, nome="ensaio", **extra):
    resposta = cliente.post("/formularios", json={"nome": nome, "definicao": DEFINICAO, **extra})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _erro(resposta, status: int) -> dict:
    assert resposta.status_code == status, resposta.text
    corpo = resposta.json()
    assert set(corpo) == {"detalhe", "erros"}
    return corpo


# --- criar e listar ---


def test_cria_pasta_na_raiz_com_o_formato_do_contrato(cliente):
    # act
    resposta = cliente.post("/pastas", json={"nome": "Obras"})

    # assert
    assert resposta.status_code == 201
    assert resposta.json() == {
        "id": resposta.json()["id"],
        "nome": "Obras",
        "pasta_pai_id": None,
        "criado_em": CRIADO_EM,
    }


def test_cria_subpasta_e_lista_em_lista_plana(cliente):
    # arrange
    obras = _pasta(cliente)
    fundacao = _pasta(cliente, "Fundação", obras["id"])

    # act
    lista = cliente.get("/pastas").json()

    # assert
    assert [(p["nome"], p["pasta_pai_id"]) for p in lista] == [
        ("Obras", None),
        ("Fundação", obras["id"]),
    ]
    assert fundacao["pasta_pai_id"] == obras["id"]


def test_nome_repetido_entre_irmas_vira_422_no_campo_nome(cliente):
    # arrange
    _pasta(cliente)

    # act
    resposta = cliente.post("/pastas", json={"nome": " obras "})

    # assert
    corpo = _erro(resposta, 422)
    assert corpo["erros"] == [
        {
            "campo": "nome",
            "mensagem": "Já existe uma pasta com este nome neste local.",
            "posicao": None,
        }
    ]


def test_pasta_pai_inexistente_vira_422_no_campo_pasta_pai_id(cliente):
    # act
    resposta = cliente.post("/pastas", json={"nome": "Obras", "pasta_pai_id": 99})

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["pasta_pai_id"]


def test_pasta_sem_nome_vira_422_no_campo_nome(cliente):
    # act
    resposta = cliente.post("/pastas", json={"nome": "  "})

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["nome"]


# --- renomear e mover (PUT substitui os dois campos) ---


def test_put_renomeia_e_move_a_pasta(cliente):
    # arrange
    obras = _pasta(cliente)
    lab = _pasta(cliente, "Laboratório")
    ensaios = _pasta(cliente, "Ensaios", obras["id"])

    # act
    resposta = cliente.put(
        f"/pastas/{ensaios['id']}", json={"nome": "Ensaios 2026", "pasta_pai_id": lab["id"]}
    )

    # assert
    assert resposta.status_code == 200
    assert resposta.json() == {
        "id": ensaios["id"],
        "nome": "Ensaios 2026",
        "pasta_pai_id": lab["id"],
        "criado_em": CRIADO_EM,
    }


def test_put_com_pasta_pai_nula_leva_a_pasta_para_a_raiz(cliente):
    # arrange
    obras = _pasta(cliente)
    ensaios = _pasta(cliente, "Ensaios", obras["id"])

    # act
    resposta = cliente.put(
        f"/pastas/{ensaios['id']}", json={"nome": "Ensaios", "pasta_pai_id": None}
    )

    # assert
    assert resposta.json()["pasta_pai_id"] is None


def test_put_sem_pasta_pai_id_e_422_para_nao_mover_para_a_raiz_sem_querer(cliente):
    # arrange
    obras = _pasta(cliente)
    ensaios = _pasta(cliente, "Ensaios", obras["id"])

    # act: o PUT substitui os dois campos; omitir um é erro, não "deixa como está"
    resposta = cliente.put(f"/pastas/{ensaios['id']}", json={"nome": "Ensaios"})

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["pasta_pai_id"]


def test_put_para_dentro_de_uma_descendente_vira_422_no_campo_pasta_pai_id(cliente):
    # arrange
    a = _pasta(cliente, "a")
    b = _pasta(cliente, "b", a["id"])

    # act
    resposta = cliente.put(f"/pastas/{a['id']}", json={"nome": "a", "pasta_pai_id": b["id"]})

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["pasta_pai_id"]


def test_put_com_nome_repetido_no_destino_vira_422_no_campo_nome(cliente):
    # arrange
    _pasta(cliente, "Ensaios")
    obras = _pasta(cliente)
    ensaios = _pasta(cliente, "Ensaios", obras["id"])

    # act
    resposta = cliente.put(
        f"/pastas/{ensaios['id']}", json={"nome": "Ensaios", "pasta_pai_id": None}
    )

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["nome"]


def test_put_em_pasta_inexistente_e_404(cliente):
    # act
    resposta = cliente.put("/pastas/99", json={"nome": "x", "pasta_pai_id": None})

    # assert
    _erro(resposta, 404)


# --- excluir ---


def test_exclui_pasta_vazia_com_204(cliente):
    # arrange
    obras = _pasta(cliente)

    # act
    resposta = cliente.delete(f"/pastas/{obras['id']}")

    # assert
    assert resposta.status_code == 204
    assert cliente.get("/pastas").json() == []


def test_excluir_pasta_com_subpasta_ou_formulario_e_409(cliente):
    # arrange
    com_subpasta = _pasta(cliente, "Com subpasta")
    _pasta(cliente, "Filha", com_subpasta["id"])
    com_formulario = _pasta(cliente, "Com formulário")
    _formulario(cliente, pasta_id=com_formulario["id"])

    # act
    por_subpasta = cliente.delete(f"/pastas/{com_subpasta['id']}")
    por_formulario = cliente.delete(f"/pastas/{com_formulario['id']}")

    # assert
    assert "subpasta" in _erro(por_subpasta, 409)["detalhe"]
    assert "formulário" in _erro(por_formulario, 409)["detalhe"]
    assert len(cliente.get("/pastas").json()) == 3  # nada em cascata


def test_excluir_pasta_inexistente_e_404(cliente):
    # act
    resposta = cliente.delete("/pastas/99")

    # assert
    _erro(resposta, 404)


# --- formulários dentro de pastas ---


def test_formulario_sem_pasta_aparece_na_raiz_na_listagem(cliente):
    # arrange
    criado = _formulario(cliente)

    # act
    lista = cliente.get("/formularios").json()

    # assert
    assert lista[0]["id"] == criado["id"] and lista[0]["pasta_id"] is None


def test_cria_formulario_ja_dentro_de_uma_pasta(cliente):
    # arrange
    obras = _pasta(cliente)

    # act
    criado = _formulario(cliente, pasta_id=obras["id"])

    # assert
    lista = cliente.get("/formularios").json()
    assert [(f["id"], f["pasta_id"]) for f in lista] == [(criado["id"], obras["id"])]


def test_criar_formulario_em_pasta_inexistente_e_422_e_nao_cria_nada(cliente):
    # act
    resposta = cliente.post(
        "/formularios", json={"nome": "ensaio", "definicao": DEFINICAO, "pasta_id": 99}
    )

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["pasta_id"]
    assert cliente.get("/formularios").json() == []


def test_move_o_formulario_para_a_pasta_e_de_volta_para_a_raiz(cliente):
    # arrange
    obras = _pasta(cliente)
    criado = _formulario(cliente)

    # act
    para_dentro = cliente.put(f"/formularios/{criado['id']}/pasta", json={"pasta_id": obras["id"]})
    para_a_raiz = cliente.put(f"/formularios/{criado['id']}/pasta", json={"pasta_id": None})

    # assert: devolve o resumo do formulário já com a pasta nova
    assert para_dentro.status_code == 200
    assert para_dentro.json() == {
        "id": criado["id"],
        "nome": "ensaio",
        "criado_em": CRIADO_EM,
        "versao_atual_id": criado["versao_atual"]["id"],
        "versao_atual_numero": 1,
        "pasta_id": obras["id"],
    }
    assert para_a_raiz.json()["pasta_id"] is None


def test_mover_formulario_para_pasta_inexistente_e_422_no_campo_pasta_id(cliente):
    # arrange
    criado = _formulario(cliente)

    # act
    resposta = cliente.put(f"/formularios/{criado['id']}/pasta", json={"pasta_id": 99})

    # assert
    corpo = _erro(resposta, 422)
    assert [e["campo"] for e in corpo["erros"]] == ["pasta_id"]


def test_mover_formulario_inexistente_e_404(cliente):
    # act
    resposta = cliente.put("/formularios/99/pasta", json={"pasta_id": None})

    # assert
    _erro(resposta, 404)


def test_mover_formulario_sem_pasta_id_no_corpo_e_422(cliente):
    # arrange
    criado = _formulario(cliente)

    # act
    resposta = cliente.put(f"/formularios/{criado['id']}/pasta", json={})

    # assert
    _erro(resposta, 422)


def test_pastas_exigem_o_token(app):
    # act
    resposta = TestClient(app).get("/pastas")

    # assert
    assert resposta.status_code == 401
