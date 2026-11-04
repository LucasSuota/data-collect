"""Rotas de IA por equipe: configuração, uso, reindexação e o chat em SSE (AGENTS.md §2.5)."""

import json

import pytest

from conftest import AGORA, cliente_da_pessoa, criar_pessoa_na_equipe
from forms import banco
from forms.api import criar_app, descobrir_extensoes
from forms.api_dependencias import obter_agora
from forms.ia import configuracao
from forms.ia import extensao as extensao_ia
from forms.ia.cliente import ClienteFalso, IaIndisponivel
from forms.segredos import Cifra, nova_chave_mestra

DEFINICAO = {"campos": [{"id": "obs", "tipo": "texto", "rotulo": "Observação"}]}
CHAVE_MESTRA = nova_chave_mestra()


@pytest.fixture
def app_ia(configuracao, validador, dsn):
    pool = banco.criar_pool(dsn, tamanho_maximo=4)
    app = criar_app(configuracao, extensoes=descobrir_extensoes(), pool=pool, validador=validador)
    app.dependency_overrides[obter_agora] = lambda: AGORA
    app.dependency_overrides[extensao_ia.obter_cifra] = lambda: Cifra([CHAVE_MESTRA])
    yield app
    pool.close()


@pytest.fixture
def adm(app_ia, chave_privada, pessoa):
    return cliente_da_pessoa(app_ia, chave_privada, pessoa)


def _config(**mudancas):
    base = {
        "ativa": True,
        "aceite_do_aviso": True,
        "provedor": "openai_compativel",
        "base_url": "http://localhost:11434/v1",
        "modelo": "llama3",
    }
    return base | mudancas


def _eventos(resposta) -> list[dict]:
    assert resposta.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(bloco.removeprefix("data: "))
        for bloco in resposta.text.split("\n\n")
        if bloco.startswith("data: ")
    ]


def _com_llm(app, llm: ClienteFalso | None):
    app.dependency_overrides[extensao_ia.obter_cliente_opcional_da_equipe] = lambda: llm


# --- configuração ---


def test_ia_nasce_desligada_e_a_configuracao_nunca_traz_a_chave(adm):
    # act
    inicial = adm.get("/ia").json()
    adm.put("/ia", json=_config(chave="sk-segredo-da-equipe"))
    depois = adm.get("/ia")

    # assert
    assert inicial["ativa"] is False and inicial["chave_definida"] is False
    assert depois.json()["chave_definida"] is True and depois.json()["ativa"] is True
    assert "sk-segredo" not in depois.text and "chave" not in {
        k for k in depois.json() if k != "chave_definida"
    }


def test_ligar_sem_aceite_e_422_no_campo_e_nada_e_gravado(adm):
    # act
    resposta = adm.put("/ia", json=_config(aceite_do_aviso=False))

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "aceite_do_aviso"
    assert adm.get("/ia").json()["ativa"] is False


def test_endereco_invalido_e_422_no_campo_base_url(adm):
    # act
    resposta = adm.put("/ia", json=_config(base_url="ftp://x"))

    # assert
    assert resposta.status_code == 422 and resposta.json()["erros"][0]["campo"] == "base_url"


def test_provedor_fora_da_lista_e_422(adm):
    # act / assert
    assert adm.put("/ia", json=_config(provedor="outro")).status_code == 422


def test_so_quem_edita_cargos_configura_a_ia(app_ia, chave_privada, adm, pessoa, dsn):
    # arrange
    engenheira = cliente_da_pessoa(
        app_ia,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "eng", "Engenheiro", int(pessoa["grupo_id"])),
    )

    # act / assert: Engenheiro usa a IA, mas não a configura
    assert engenheira.get("/ia").status_code == 403
    assert engenheira.put("/ia", json=_config()).status_code == 403
    assert engenheira.get("/ia/uso").status_code == 403


def test_configuracao_de_uma_equipe_nao_aparece_na_outra(app_ia, chave_privada, adm, dsn):
    # arrange
    adm.put("/ia", json=_config(chave="sk-da-a"))
    outra = cliente_da_pessoa(app_ia, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))

    # act / assert
    assert outra.get("/ia").json()["ativa"] is False


def test_sem_chave_mestra_no_servidor_a_chave_e_recusada_em_portugues(app_ia, adm):
    # arrange
    app_ia.dependency_overrides[extensao_ia.obter_cifra] = lambda: None

    # act
    resposta = adm.put("/ia", json=_config(chave="sk-1"))

    # assert
    assert resposta.status_code == 422 and "chave-mestra" in resposta.json()["detalhe"]


def test_testar_conexao_mostra_sucesso_ou_o_motivo_sem_vazar_a_chave(adm, monkeypatch):
    # arrange
    adm.put("/ia", json=_config(chave="sk-segredo"))
    monkeypatch.setattr(
        configuracao, "criar_cliente_da_equipe", lambda *a, **k: ClienteFalso(["ok"])
    )

    # act
    certo = adm.post("/ia/testar").json()

    def falha(*a, **k):
        raise IaIndisponivel("Não foi possível consultar a IA agora.")

    monkeypatch.setattr(configuracao, "criar_cliente_da_equipe", falha)
    errado = adm.post("/ia/testar").json()

    # assert
    assert certo["ok"] is True and errado["ok"] is False
    assert "sk-segredo" not in errado["mensagem"]


def test_uso_mostra_so_contagens_e_os_limites(adm):
    # act
    uso = adm.get("/ia/uso").json()

    # assert
    assert uso["chamadas_da_equipe"] == 0 and uso["limite_de_chamadas_por_pessoa"] == 300
    assert set(uso) == {
        "chamadas_da_pessoa",
        "chamadas_da_equipe",
        "tokens_da_equipe",
        "limite_de_chamadas_por_pessoa",
        "limite_de_chamadas_por_equipe",
        "limite_de_tokens_por_equipe",
    }


def test_reindexar_conta_o_que_foi_indexado(app_ia, adm):
    # arrange
    f = adm.post("/formularios", json={"nome": "Diário", "definicao": DEFINICAO}).json()
    adm.post(
        f"/formularios/{f['id']}/registros",
        json={"versao_id": f["versao_atual"]["id"], "dados": {"obs": "concretagem"}},
    )
    _com_llm(app_ia, None)

    # act
    primeira = adm.post("/ia/reindexar").json()
    segunda = adm.post("/ia/reindexar").json()

    # assert
    assert primeira["gravados"] == 2 and primeira["vetorizados"] == 0
    assert segunda["gravados"] == 2  # recria tudo: é a reindexação completa


# --- chat ---


def test_chat_sem_ia_responde_com_o_que_o_codigo_achou_e_diz_que_nao_ha_ia(app_ia, adm):
    # arrange
    f = adm.post("/formularios", json={"nome": "Diário", "definicao": DEFINICAO}).json()
    adm.post(
        f"/formularios/{f['id']}/registros",
        json={"versao_id": f["versao_atual"]["id"], "dados": {"obs": "concretagem da laje"}},
    )
    _com_llm(app_ia, None)

    # act
    resposta = adm.post("/chat", json={"mensagem": "concretagem laje"})
    eventos = _eventos(resposta)

    # assert
    assert eventos[0]["tipo"] == "conversa"
    texto = "".join(e["texto"] for e in eventos if e["tipo"] == "texto")
    assert "concretagem da laje" in texto
    fim = eventos[-1]
    assert fim["tipo"] == "fim" and fim["usou_ia"] is False and fim["ia_disponivel"] is False
    assert fim["citacoes"][0]["tipo"] == "registro"


def test_chat_com_ia_devolve_texto_conferido_em_pedacos(app_ia, adm):
    # arrange
    f = adm.post("/formularios", json={"nome": "Diário", "definicao": DEFINICAO}).json()
    adm.post(
        f"/formularios/{f['id']}/registros",
        json={"versao_id": f["versao_atual"]["id"], "dados": {"obs": "concretagem da laje"}},
    )
    llm = ClienteFalso(
        [
            json.dumps({"acao": "buscar", "consulta": "concretagem"}),
            "Há um registro sobre concretagem da laje (registro #1).",
        ]
    )
    _com_llm(app_ia, llm)

    # act
    eventos = _eventos(adm.post("/chat", json={"mensagem": "algo sobre concretagem?"}))

    # assert
    textos = [e["texto"] for e in eventos if e["tipo"] == "texto"]
    assert len(textos) > 1  # em pedaços
    assert "".join(textos) == "Há um registro sobre concretagem da laje (registro #1)."
    assert eventos[-1]["usou_ia"] is True and eventos[-1]["ia_disponivel"] is True


def test_conversas_ficam_salvas_por_pessoa_e_so_a_dona_as_ve(
    app_ia, chave_privada, adm, pessoa, dsn
):
    # arrange
    _com_llm(app_ia, None)
    conversa = _eventos(adm.post("/chat", json={"mensagem": "como exportar?"}))[0]["conversa_id"]
    colega = cliente_da_pessoa(
        app_ia,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "colega", "Administrador", int(pessoa["grupo_id"])),
    )

    # act
    minhas = adm.get("/chat/conversas").json()
    lida = adm.get(f"/chat/conversas/{conversa}").json()

    # assert
    assert [c["id"] for c in minhas] == [conversa] and minhas[0]["titulo"] == "como exportar?"
    assert [m["papel"] for m in lida["mensagens"]] == ["pessoa", "assistente"]
    assert colega.get("/chat/conversas").json() == []
    assert colega.get(f"/chat/conversas/{conversa}").status_code == 404
    assert colega.delete(f"/chat/conversas/{conversa}").status_code == 404
    assert colega.post("/chat", json={"mensagem": "oi", "conversa_id": conversa}).status_code == 404


def test_apagar_conversa_remove_tambem_as_mensagens(app_ia, adm, dsn):
    # arrange
    _com_llm(app_ia, None)
    conversa = _eventos(adm.post("/chat", json={"mensagem": "como exportar?"}))[0]["conversa_id"]

    # act
    apagou = adm.delete(f"/chat/conversas/{conversa}")

    # assert
    assert apagou.status_code == 204 and adm.get(f"/chat/conversas/{conversa}").status_code == 404
    con = banco.abrir_conexao(dsn)
    assert con.execute("SELECT COUNT(*) AS n FROM mensagens_ia").fetchone()["n"] == 0
    con.close()


def test_continuar_a_conversa_acrescenta_mensagens(app_ia, adm):
    # arrange
    _com_llm(app_ia, None)
    conversa = _eventos(adm.post("/chat", json={"mensagem": "primeira"}))[0]["conversa_id"]

    # act
    _eventos(adm.post("/chat", json={"mensagem": "segunda", "conversa_id": conversa}))

    # assert
    assert len(adm.get(f"/chat/conversas/{conversa}").json()["mensagens"]) == 4


def test_pergunta_vazia_ou_grande_demais_e_422(adm):
    # act / assert
    assert adm.post("/chat", json={"mensagem": ""}).status_code == 422
    assert adm.post("/chat", json={"mensagem": "x" * 1001}).status_code == 422


def test_chat_exige_a_permissao_do_assistente(app_ia, chave_privada, pessoa, dsn):
    # arrange
    visualizador = cliente_da_pessoa(
        app_ia,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "vis", "Visualizador", int(pessoa["grupo_id"])),
    )

    # act / assert
    assert visualizador.post("/chat", json={"mensagem": "oi"}).status_code == 403


def test_gerador_e_resumo_usam_o_provedor_da_equipe_e_ia_desligada_vira_503(app_ia, adm):
    # act: sem ligar a IA da equipe, o gerador não pode enviar nada
    resposta = adm.post("/definicoes/gerar", json={"pedido": "um formulário"})

    # assert
    assert (
        resposta.status_code == 503 and "desligada para esta equipe" in resposta.json()["detalhe"]
    )


def test_chat_cai_no_limite_de_taxa_com_429(app_ia, adm, monkeypatch):
    # arrange
    from forms import api_seguranca

    _com_llm(app_ia, None)
    monkeypatch.setitem(
        api_seguranca.LIMITES_POR_ROTA, ("POST", "/chat"), api_seguranca.Limite(1, 60)
    )
    monkeypatch.setattr("forms.api_dependencias.LIMITES_POR_ROTA", api_seguranca.LIMITES_POR_ROTA)

    # act
    primeira = adm.post("/chat", json={"mensagem": "como exportar?"})
    segunda = adm.post("/chat", json={"mensagem": "como exportar?"})

    # assert
    assert primeira.status_code == 200 and segunda.status_code == 429
