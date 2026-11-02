from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forms.api import Configuracao, criar_app

# Os mesmos valores do conftest.py (`tests/` não é um pacote, então não dá para importar).
TOKEN = "token-de-teste"
ORIGEM_PERMITIDA = "http://localhost:5173"


def _erro_uniforme(resposta) -> dict:
    corpo = resposta.json()
    assert set(corpo) == {"detalhe", "erros"}
    assert isinstance(corpo["detalhe"], str) and isinstance(corpo["erros"], list)
    return corpo


# --- token por execução ---


def test_sem_token_a_api_responde_401_no_formato_uniforme(app):
    # act
    resposta = TestClient(app).get("/formularios")

    # assert
    assert resposta.status_code == 401
    assert "Token" in _erro_uniforme(resposta)["detalhe"]


def test_token_errado_responde_401_com_a_mesma_mensagem_do_ausente(app):
    # act
    ausente = TestClient(app).get("/formularios")
    errado = TestClient(app, headers={"X-Forms-Token": "outro"}).get("/formularios")

    # assert: não ensina nada a quem tenta adivinhar
    assert errado.status_code == 401 and errado.json() == ausente.json()


def test_token_certo_passa(cliente):
    # act / assert
    assert cliente.get("/formularios").status_code == 200


@pytest.mark.parametrize(
    "caminho", ["/catalogo", "/formularios", "/registros/1", "/anexos/1", "/openapi.json", "/docs"]
)
def test_o_token_vale_para_todo_caminho_inclusive_a_documentacao(app, caminho):
    # act / assert
    assert TestClient(app).get(caminho).status_code == 401


def test_token_dispensado_por_configuracao_em_desenvolvimento(configuracao):
    # arrange
    dev = Configuracao(
        banco=configuracao.banco,
        pasta_de_dados=configuracao.pasta_de_dados,
        token=None,
        dispensar_token=True,
        origens_cors=configuracao.origens_cors,
    )

    # act / assert
    assert TestClient(criar_app(dev)).get("/formularios").status_code == 200


def test_sem_token_configurado_e_sem_dispensa_a_api_recusa_tudo(configuracao):
    # arrange: esquecer de configurar o token não pode abrir a API
    sem_token = Configuracao(
        banco=configuracao.banco,
        pasta_de_dados=configuracao.pasta_de_dados,
        token=None,
        dispensar_token=False,
        origens_cors=configuracao.origens_cors,
    )

    # act
    cliente = TestClient(criar_app(sem_token), headers={"X-Forms-Token": ""})

    # assert
    assert cliente.get("/formularios").status_code == 401


def test_token_vazio_nunca_autentica(app):
    # act / assert
    assert TestClient(app, headers={"X-Forms-Token": ""}).get("/formularios").status_code == 401


# --- CORS restrito ---


def test_origem_do_front_recebe_os_cabecalhos_cors(cliente):
    # act
    resposta = cliente.get("/formularios", headers={"Origin": ORIGEM_PERMITIDA})

    # assert
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
    assert "access-control-allow-credentials" not in resposta.headers


def test_origem_nao_listada_nao_recebe_cors(cliente):
    # act
    resposta = cliente.get("/formularios", headers={"Origin": "http://malicioso.example"})

    # assert
    assert "access-control-allow-origin" not in resposta.headers


def test_preflight_passa_sem_token_e_so_para_a_origem_permitida(app):
    # arrange: o navegador não manda o token no preflight (OPTIONS)
    cabecalhos = {
        "Origin": ORIGEM_PERMITIDA,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-forms-token,content-type",
    }

    # act
    permitida = TestClient(app).options("/formularios", headers=cabecalhos)
    negada = TestClient(app).options(
        "/formularios", headers=cabecalhos | {"Origin": "http://x.example"}
    )

    # assert
    assert permitida.status_code == 200
    assert permitida.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
    assert "x-forms-token" in permitida.headers["access-control-allow-headers"].lower()
    assert negada.status_code == 400 and "access-control-allow-origin" not in negada.headers


def test_o_401_tambem_leva_os_cabecalhos_cors_para_o_front_conseguir_ler_o_erro(app):
    # act
    resposta = TestClient(app).get("/formularios", headers={"Origin": ORIGEM_PERMITIDA})

    # assert
    assert resposta.status_code == 401
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA


def test_cors_nunca_aceita_asterisco(tmp_path: Path):
    # act / assert
    with pytest.raises(ValueError, match="nunca"):
        Configuracao(tmp_path / "a.db", tmp_path, TOKEN, False, ("*",))


def test_configuracao_do_ambiente_usa_as_duas_origens_do_vite_por_padrao():
    # act
    configuracao = Configuracao.do_ambiente({})

    # assert
    assert configuracao.origens_cors == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert configuracao.token is None and configuracao.dispensar_token is False


def test_configuracao_le_banco_pasta_token_e_origens_do_ambiente():
    # act
    configuracao = Configuracao.do_ambiente(
        {
            "FORMS_DB_PATH": "/dados/x.db",
            "FORMS_DATA_DIR": "/dados/anexos",
            "FORMS_TOKEN": "abc",
            "FORMS_SKIP_TOKEN": "true",
            "FORMS_CORS_ORIGINS": "http://a.example, http://b.example",
        }
    )

    # assert
    assert configuracao.banco == Path("/dados/x.db") and configuracao.pasta_de_dados == Path(
        "/dados/anexos"
    )
    assert configuracao.token == "abc" and configuracao.dispensar_token is True
    assert configuracao.origens_cors == ("http://a.example", "http://b.example")


def test_configuracao_sem_pasta_usa_a_pasta_do_banco():
    # act
    configuracao = Configuracao.do_ambiente({"FORMS_DB_PATH": "/dados/x.db"})

    # assert: o `resolve()` do código completa o caminho; no Windows `/dados` vira `D:\dados`
    assert configuracao.pasta_de_dados == Path("/dados").resolve()


# --- formato de erro uniforme ---


def test_caminho_inexistente_e_metodo_errado_seguem_o_formato_uniforme(cliente):
    # act
    nao_existe = cliente.get("/nada")
    metodo = cliente.put("/formularios")

    # assert
    assert (
        nao_existe.status_code == 404
        and _erro_uniforme(nao_existe)["detalhe"] == "Recurso não encontrado."
    )
    assert (
        metodo.status_code == 405 and _erro_uniforme(metodo)["detalhe"] == "Método não permitido."
    )


def test_erro_do_pydantic_vira_422_uniforme_em_portugues_com_o_campo_certo(cliente):
    # act
    resposta = cliente.post("/formularios", json={"definicao": {"campos": []}})  # falta o nome

    # assert
    corpo = _erro_uniforme(resposta)
    assert resposta.status_code == 422
    assert corpo["erros"] == [{"campo": "nome", "mensagem": "Campo obrigatório.", "posicao": None}]


def test_corpo_que_nao_e_json_vira_422_uniforme(cliente):
    # act
    resposta = cliente.post(
        "/formularios", content=b"{nao e json", headers={"Content-Type": "application/json"}
    )

    # assert
    assert resposta.status_code == 422
    assert "JSON" in _erro_uniforme(resposta)["erros"][0]["mensagem"]


def test_parametro_de_consulta_invalido_vira_422_uniforme(cliente):
    # act
    resposta = cliente.get("/formularios/1/registros", params={"limite": 500})

    # assert
    assert resposta.status_code == 422
    assert _erro_uniforme(resposta)["erros"][0]["campo"] == "limite"


def test_id_que_nao_e_numero_vira_422_uniforme(cliente):
    # act
    resposta = cliente.get("/formularios/abc")

    # assert
    assert (
        resposta.status_code == 422
        and _erro_uniforme(resposta)["erros"][0]["campo"] == "formulario_id"
    )


def test_campo_extra_no_corpo_e_recusado_em_vez_de_ignorado(cliente):
    # act
    resposta = cliente.post(
        "/formularios", json={"nome": "a", "definicao": {"campos": []}, "extra": 1}
    )

    # assert
    assert resposta.status_code == 422
    assert _erro_uniforme(resposta)["erros"][0] == {
        "campo": "extra",
        "mensagem": "Este campo não existe.",
        "posicao": None,
    }


def test_erro_inesperado_vira_500_uniforme_sem_vazar_a_causa(configuracao, monkeypatch):
    # arrange
    from forms import servico

    def explodir(*argumentos, **nomeados):
        raise RuntimeError("segredo interno /etc/passwd")

    monkeypatch.setattr(servico, "listar_formularios", explodir)
    cliente = TestClient(
        criar_app(configuracao), headers={"X-Forms-Token": TOKEN}, raise_server_exceptions=False
    )

    # act
    resposta = cliente.get("/formularios")

    # assert
    assert resposta.status_code == 500
    assert (
        "segredo" not in resposta.text
        and _erro_uniforme(resposta)["detalhe"] == "Erro interno do servidor."
    )


def test_importar_o_modulo_nao_cria_arquivo_nem_abre_banco(tmp_path, monkeypatch):
    # arrange
    monkeypatch.chdir(tmp_path)

    # act
    import importlib

    import forms.api

    importlib.reload(forms.api)

    # assert
    assert list(tmp_path.iterdir()) == []
