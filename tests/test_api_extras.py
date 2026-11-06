"""Início, busca, avisos, tour, exemplos, histórico e direitos da pessoa pela API
(AGENTS.md §2.14 a §2.18)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import cliente_da_pessoa, criar_pessoa_na_equipe
from forms.infra.logto import ClienteLogto, IdentidadeIndisponivel

DEFINICAO = {
    "campos": [
        {"id": "carga", "tipo": "numero", "rotulo": "Carga", "unidade": "kN"},
        {"id": "ok", "tipo": "calculado", "rotulo": "Conforme?", "formula": "carga >= 10"},
        {"id": "obs", "tipo": "texto", "rotulo": "Observação"},
        {"id": "fase", "tipo": "selecao", "rotulo": "Fase", "opcoes": ["Moldagem", "Ruptura"]},
    ]
}


@pytest.fixture
def formulario(cliente):
    return cliente.post(
        "/formularios", json={"nome": "Corpo de prova", "definicao": DEFINICAO}
    ).json()


def _novo(cliente, formulario, **dados):
    resposta = cliente.post(
        f"/formularios/{formulario['id']}/registros",
        json={"versao_id": formulario["versao_atual"]["id"], "dados": dados},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# --- /healthz e /readyz ---


def test_healthz_e_readyz_respondem_sem_token_e_sem_vazar_detalhe(app):
    # act
    cliente = TestClient(app)
    saude, pronto = cliente.get("/healthz"), cliente.get("/readyz")

    # assert
    assert saude.json() == {"status": "ok"}
    assert pronto.status_code == 200 and pronto.json()["status"] == "ok"
    assert set(pronto.json()) == {"status", "migracao"}


# --- registros: autoria, revisão, histórico, contagens ---


def test_registro_traz_autoria_com_nome_e_revisao(cliente, formulario, pessoa):
    # act
    criado = _novo(cliente, formulario, carga="12")

    # assert
    assert criado["revisao"] == 1
    assert criado["criado_por"] == {"id": pessoa["usuario_id"], "nome": "ana"}
    assert criado["atualizado_por"]["nome"] == "ana"


def test_put_com_revisao_desatualizada_e_409_com_codigo_e_mensagem(cliente, formulario):
    # arrange
    registro = _novo(cliente, formulario, carga="1")
    cliente.put(f"/registros/{registro['id']}", json={"dados": {"carga": "2"}, "revisao": 1})

    # act
    conflito = cliente.put(
        f"/registros/{registro['id']}", json={"dados": {"carga": "3"}, "revisao": 1}
    )

    # assert
    assert conflito.status_code == 409 and conflito.json()["codigo"] == "revisao_desatualizada"
    assert "ana alterou" in conflito.json()["detalhe"]
    assert cliente.get(f"/registros/{registro['id']}").json()["dados"]["carga"] == "2"


def test_put_sem_revisao_e_422(cliente, formulario):
    # arrange
    registro = _novo(cliente, formulario)

    # act
    resposta = cliente.put(f"/registros/{registro['id']}", json={"dados": {}})

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "revisao"


def test_historico_pela_api_traz_quem_quando_e_o_que_havia(cliente, formulario):
    # arrange
    registro = _novo(cliente, formulario, carga="1")
    cliente.put(f"/registros/{registro['id']}", json={"dados": {"carga": "2"}, "revisao": 1})

    # act
    historico = cliente.get(f"/registros/{registro['id']}/historico").json()

    # assert
    assert [h["acao"] for h in historico] == ["editado", "criado"]
    assert historico[0]["pessoa"] == "ana" and historico[0]["valores_anteriores"]["carga"] == "1"


def test_listagem_traz_estado_exibicao_e_filtro_dos_meus(
    app, chave_privada, cliente, formulario, pessoa, dsn
):
    # arrange
    _novo(cliente, formulario, carga="12")
    _novo(cliente, formulario, carga="3")
    colega = cliente_da_pessoa(
        app,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "colega", "Técnico", int(pessoa["grupo_id"])),
    )
    _novo(colega, formulario, carga="20")

    # act
    todos = cliente.get(f"/formularios/{formulario['id']}/registros").json()
    meus = cliente.get(f"/formularios/{formulario['id']}/registros?meus=true").json()

    # assert
    assert sorted(r["estado"] for r in todos["itens"]) == ["conforme", "conforme", "nao_conforme"]
    assert todos["exibicao"] == {"destaque": "ok" if False else None, "status": "ok", "resumo": []}
    assert meus["total"] == 2


def test_contagens_pela_api_com_os_mesmos_filtros(cliente, formulario):
    # arrange
    _novo(cliente, formulario, carga="12", fase="Moldagem")
    _novo(cliente, formulario, carga="3", fase="Moldagem")
    _novo(cliente, formulario, carga="30", fase="Ruptura")

    # act
    todas = cliente.get(f"/formularios/{formulario['id']}/registros/contagens").json()
    filtradas = cliente.get(
        f"/formularios/{formulario['id']}/registros/contagens?filtro=fase:Moldagem"
    ).json()

    # assert
    assert todas == {
        "campo_status": "ok",
        "total": 3,
        "conforme": 2,
        "nao_conforme": 1,
        "erro": 0,
        "aguardando": 0,
    }
    assert (filtradas["total"], filtradas["conforme"]) == (2, 1)


def test_definicao_com_exibicao_e_ia_volta_como_foi_escrita(cliente):
    # arrange
    definicao = {
        **DEFINICAO,
        "campos": [
            *DEFINICAO["campos"],
            {"id": "cpf", "tipo": "texto", "rotulo": "CPF", "ia": False},
        ],
        "exibicao": {"destaque": "carga", "status": "ok", "resumo": ["obs"]},
    }

    # act
    criado = cliente.post("/formularios", json={"nome": "x", "definicao": definicao}).json()

    # assert
    devolvida = criado["versao_atual"]["definicao"]
    assert devolvida["exibicao"] == {"destaque": "carga", "status": "ok", "resumo": ["obs"]}
    assert devolvida["campos"][-1]["ia"] is False and "ia" not in devolvida["campos"][0]


def test_exibicao_invalida_e_422_com_o_campo(cliente):
    # act
    resposta = cliente.post(
        "/formularios",
        json={"nome": "x", "definicao": {**DEFINICAO, "exibicao": {"status": "carga"}}},
    )

    # assert
    assert resposta.status_code == 422
    assert resposta.json()["erros"][0]["campo"] == "exibicao.status"


# --- busca ---


def test_busca_acha_formulario_por_nome_e_registro_por_id_e_por_texto(cliente, formulario):
    # arrange
    registro = _novo(cliente, formulario, obs="Concretagem da laje do 3º andar", carga="12")
    _novo(cliente, formulario, obs="outra coisa", carga="30")

    # act
    por_nome = cliente.get("/busca?q=corpo").json()
    por_id = cliente.get(f"/busca?q=%23{registro['id']}").json()
    por_texto = cliente.get("/busca?q=laje").json()

    # assert
    assert [f["nome"] for f in por_nome["formularios"]] == ["Corpo de prova"]
    assert por_id["registros"][0]["id"] == registro["id"]
    assert [r["id"] for r in por_texto["registros"]] == [registro["id"]]
    assert por_texto["registros"][0]["formulario"] == "Corpo de prova"


def test_busca_nao_olha_numero_nem_chaves_do_json(cliente, formulario):
    # arrange
    _novo(cliente, formulario, carga="12345", obs="x")

    # act / assert: "12345" é número (guardado como texto) e "obs" é nome de campo
    assert cliente.get("/busca?q=12345").json()["registros"][0:1] == []
    assert cliente.get("/busca?q=obs").json()["registros"] == []


def test_busca_trata_curinga_e_aspas_do_termo_como_texto(cliente, formulario):
    # arrange
    _novo(cliente, formulario, obs="100% concreto_ok")

    # act
    achou = cliente.get("/busca?q=100%25 concreto_").json()["registros"]
    injecao = cliente.get("/busca", params={"q": "x'; DROP TABLE registros; --"})
    curinga = cliente.get("/busca?q=%25%25").json()["registros"]

    # assert
    assert len(achou) == 1 and injecao.status_code == 200
    assert curinga == []  # "%%" literal não casa com tudo
    assert cliente.get("/formularios").status_code == 200


def test_busca_com_termo_curto_ou_longo_demais_e_422(cliente):
    # act / assert
    assert cliente.get("/busca?q=a").status_code == 422
    assert cliente.get("/busca", params={"q": "x" * 101}).status_code == 422


def test_busca_so_mostra_o_que_o_cargo_ve(app, chave_privada, cliente, formulario, pessoa, dsn):
    # arrange: um cargo que ve registros mas não formulários
    cliente.post(
        "/cargos", json={"nome": "SoRegistros", "descricao": "", "permissoes": ["registros:ver"]}
    )
    _novo(cliente, formulario, obs="achado")
    so_registros = cliente_da_pessoa(
        app,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "sr", "SoRegistros", int(pessoa["grupo_id"])),
    )

    # act
    resultado = so_registros.get("/busca?q=corpo").json()
    por_texto = so_registros.get("/busca?q=achado").json()

    # assert
    assert resultado["formularios"] == [] and len(por_texto["registros"]) == 1


# --- registros recentes ---


def test_recentes_trazem_estado_e_valor_em_destaque_decididos_no_servidor(cliente, formulario):
    # arrange
    _novo(cliente, formulario, carga="12")

    # act
    recente = cliente.get("/registros/recentes").json()[0]

    # assert
    assert recente["formulario"] == "Corpo de prova" and recente["estado"] == "conforme"
    assert recente["destaque"] is None or recente["destaque"]["rotulo"]


# --- notificações ---


def test_notificacoes_pela_api_ate_marcar_como_lida(
    app, chave_privada, cliente, formulario, pessoa, dsn
):
    # arrange: uma colega edita o registro da ana
    registro = _novo(cliente, formulario, carga="1")
    engenheira = cliente_da_pessoa(
        app,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "eng", "Engenheiro", int(pessoa["grupo_id"])),
    )
    engenheira.put(
        f"/registros/{registro['id']}",
        json={"dados": {"carga": "2"}, "revisao": registro["revisao"]},
    )

    # act
    antes = cliente.get("/notificacoes").json()
    cliente.post(f"/notificacoes/{antes['itens'][0]['id']}/lida")
    depois = cliente.get("/notificacoes").json()

    # assert
    assert antes["nao_lidas"] == 1 and antes["itens"][0]["tipo"] == "registro_editado"
    assert depois["nao_lidas"] == 0 and depois["itens"][0]["lida"] is True


# --- tour ---


def test_progresso_do_tour_fica_no_servidor_por_pessoa(cliente):
    # arrange
    inicial = cliente.get("/eu/onboarding").json()

    # act
    cliente.put(
        "/eu/onboarding", json={"tour_concluido": True, "passo": 4, "checklist_dispensado": False}
    )
    depois = cliente.get("/eu/onboarding").json()

    # assert
    assert inicial == {"tour_concluido": False, "passo": 0, "checklist_dispensado": False}
    assert depois == {"tour_concluido": True, "passo": 4, "checklist_dispensado": False}


def test_passo_fora_do_limite_e_422(cliente):
    # act / assert
    resposta = cliente.put(
        "/eu/onboarding",
        json={"tour_concluido": False, "passo": 999, "checklist_dispensado": False},
    )
    assert resposta.status_code == 422


# --- exemplos ---


def test_galeria_lista_os_exemplos_com_as_dependencias(cliente):
    # act
    exemplos = {e["nome"]: e for e in cliente.get("/templates").json()}

    # assert
    assert {
        "corpo_de_prova",
        "inspecao_obra",
        "ensaio_umidade",
        "proctor",
        "densidade_insitu",
    } <= set(exemplos)
    assert exemplos["proctor"]["depende_de"] == ["ensaio_umidade"]
    assert exemplos["corpo_de_prova"]["campos"] > 0


def test_importar_exemplos_dependentes_em_qualquer_ordem(cliente):
    # act
    resposta = cliente.post(
        "/templates/importar", json={"nomes": ["densidade_insitu", "ensaio_umidade", "proctor"]}
    )

    # assert
    assert resposta.status_code == 201
    assert set(resposta.json()["formularios"]) == {"densidade_insitu", "ensaio_umidade", "proctor"}
    assert {f["nome"] for f in cliente.get("/formularios").json()} >= {"proctor"}


def test_exemplo_inexistente_ou_com_caminho_e_recusado_sem_tocar_no_disco(cliente):
    # act
    inexistente = cliente.post("/templates/importar", json={"nomes": ["fantasma"]})
    caminho = cliente.post("/templates/importar", json={"nomes": ["../../etc/passwd"]})

    # assert
    assert inexistente.status_code == 404 and caminho.status_code == 404


def test_importar_o_mesmo_exemplo_duas_vezes_e_422(cliente):
    # arrange
    cliente.post("/templates/importar", json={"nomes": ["inspecao_obra"]})

    # act
    segunda = cliente.post("/templates/importar", json={"nomes": ["inspecao_obra"]})

    # assert
    assert segunda.status_code == 422


# --- direitos da pessoa ---


def test_exportar_meus_dados_traz_perfil_aceites_e_o_que_criei(cliente, formulario, pessoa):
    # arrange
    _novo(cliente, formulario, carga="1")

    # act
    resposta = cliente.get("/eu/exportar")
    dados = resposta.json()

    # assert
    assert "meus-dados.json" in resposta.headers["content-disposition"]
    assert dados["pessoa"]["nome"] == "ana" and len(dados["consentimentos"]) == 2
    equipe = dados["equipes"][0]
    assert equipe["cargo"] == "Administrador" and len(equipe["registros_criados"]) == 1
    assert equipe["alteracoes_feitas"] >= 1
    assert "senha" not in json.dumps(dados).lower()


def test_excluir_minha_conta_apaga_a_pessoa_e_anonimiza_a_autoria(
    app, chave_privada, cliente, formulario, pessoa, dsn
):
    # arrange: a ana não é a única administradora, e criou um registro
    outra_admin = criar_pessoa_na_equipe(dsn, "chefe", "Administrador", int(pessoa["grupo_id"]))
    chefe = cliente_da_pessoa(app, chave_privada, outra_admin)
    registro = _novo(cliente, formulario, carga="1")

    # act
    apagou = cliente.delete("/eu")
    lido = chefe.get(f"/registros/{registro['id']}").json()

    # assert: a conta some, o trabalho fica sem nome
    assert apagou.status_code == 204
    assert lido["criado_por"] is None and lido["atualizado_por"] is None
    assert [m["nome"] for m in chefe.get("/membros").json()] == ["chefe"]
    assert chefe.get("/eu/exportar").status_code == 200


def test_unica_administradora_com_outras_pessoas_nao_pode_excluir_a_conta(
    app, chave_privada, cliente, pessoa, dsn
):
    # arrange
    criar_pessoa_na_equipe(dsn, "tec", "Técnico", int(pessoa["grupo_id"]))

    # act
    resposta = cliente.delete("/eu")

    # assert
    assert (
        resposta.status_code == 422
        and "única administradora" in resposta.json()["erros"][0]["mensagem"]
    )
    assert cliente.get("/eu").status_code == 200


def test_excluir_a_conta_tambem_apaga_no_logto_quando_configurado(app, chave_privada, pessoa, dsn):
    # arrange
    apagados: list[str] = []

    class GestorFalso:
        def perfil(self, sub):
            return None, None

        def apagar(self, sub):
            apagados.append(sub)

    app.state.gestor = GestorFalso()
    cliente = cliente_da_pessoa(app, chave_privada, pessoa)

    # act
    resposta = cliente.delete("/eu")

    # assert
    assert resposta.status_code == 204 and apagados == [pessoa["sub"]]


def test_logto_fora_do_ar_na_exclusao_devolve_502_em_portugues(app, chave_privada, pessoa):
    # arrange
    class Quebrado:
        def perfil(self, sub):
            return None, None

        def apagar(self, sub):
            raise IdentidadeIndisponivel(
                "Os dados foram removidos, mas não foi possível apagar a conta."
            )

    app.state.gestor = Quebrado()

    # act
    resposta = cliente_da_pessoa(app, chave_privada, pessoa).delete("/eu")

    # assert
    assert resposta.status_code == 502 and "removidos" in resposta.json()["detalhe"]


# --- cliente do Logto (sem rede: transporte falso) ---


def _logto(rotas) -> ClienteLogto:
    cliente = httpx.Client(transport=httpx.MockTransport(rotas))
    return ClienteLogto("https://auth.teste", "m2m-id", "m2m-segredo", cliente_http=cliente)


def test_cliente_logto_le_o_perfil_com_o_token_m2m():
    # arrange
    vistos = []

    def rotas(pedido: httpx.Request) -> httpx.Response:
        vistos.append((pedido.method, pedido.url.path, pedido.headers.get("authorization", "")))
        if pedido.url.path == "/oidc/token":
            return httpx.Response(200, json={"access_token": "t0k"})
        return httpx.Response(200, json={"name": "Ana Souza", "primaryEmail": "ana@x.io"})

    # act
    perfil = _logto(rotas).perfil("abc123")

    # assert
    assert perfil == ("Ana Souza", "ana@x.io")
    assert vistos[0][1] == "/oidc/token" and vistos[0][2].startswith("Basic ")
    assert vistos[1] == ("GET", "/api/users/abc123", "Bearer t0k")


def test_cliente_logto_perfil_de_usuario_inexistente_e_vazio_e_apagar_e_idempotente():
    # arrange
    def rotas(pedido: httpx.Request) -> httpx.Response:
        if pedido.url.path == "/oidc/token":
            return httpx.Response(200, json={"access_token": "t"})
        return httpx.Response(404)

    logto = _logto(rotas)

    # act / assert
    assert logto.perfil("x") == (None, None)
    logto.apagar("x")  # 404 = já não existe


@pytest.mark.parametrize("status", [401, 500])
def test_cliente_logto_erro_vira_erro_de_dominio_sem_vazar_o_segredo(status):
    # arrange
    logto = _logto(lambda pedido: httpx.Response(status))

    # act / assert
    with pytest.raises(IdentidadeIndisponivel) as erro:
        logto.perfil("x")
    assert "m2m-segredo" not in str(erro.value) and "m2m-segredo" not in repr(logto)
