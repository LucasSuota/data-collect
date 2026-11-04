import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from forms import servico_equipes
from forms.api import Configuracao, criar_app
from forms.auth import ALGORITMOS_ACEITOS
from forms.banco import abrir_conexao
from forms.models import Contexto

# Os mesmos valores do conftest.py (`tests/` não é um pacote, então não dá para importar).
ORIGEM_PERMITIDA = "http://localhost:5173"
AGORA_DE_TESTE = None  # o relógio das fixtures só vale para a gravação, não para a validade do JWT


def _erro_uniforme(resposta) -> dict:
    corpo = resposta.json()
    assert set(corpo) - {"codigo"} == {"detalhe", "erros"}
    assert isinstance(corpo["detalhe"], str) and isinstance(corpo["erros"], list)
    return corpo


# --- autenticação pelo token do Logto ---


def test_sem_token_a_api_responde_401_no_formato_uniforme(app):
    # act
    resposta = TestClient(app).get("/formularios")

    # assert
    assert resposta.status_code == 401
    assert _erro_uniforme(resposta)["codigo"] == "token_ausente"


def test_token_valido_passa(cliente):
    # act / assert
    assert cliente.get("/formularios").status_code == 200


def test_token_expirado_responde_401_com_codigo_proprio_para_o_front_renovar(app, emitir, pessoa):
    # arrange: expirado há dois minutos, além da folga de relógio
    token = emitir(str(pessoa["sub"]), expira_em=-120)

    # act
    resposta = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")

    # assert
    assert resposta.status_code == 401 and resposta.json()["codigo"] == "token_expirado"


def test_a_folga_de_relogio_aceita_um_token_que_acabou_de_vencer(app, emitir, pessoa):
    # arrange: venceu há 10 s, dentro dos 30 s de folga
    token = emitir(str(pessoa["sub"]), expira_em=-10)
    cabecalhos = {"Authorization": f"Bearer {token}", "X-Equipe": str(pessoa["grupo_id"])}

    # act / assert
    assert TestClient(app, headers=cabecalhos).get("/formularios").status_code == 200


def test_token_sem_exp_e_recusado(app, chave_privada, pessoa):
    # arrange
    token = jwt.encode(
        {"sub": "x", "iss": "https://logto.teste/oidc", "aud": "https://api.teste"},
        chave_privada,
        algorithm="ES384",
    )

    # act / assert
    resposta = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")
    assert resposta.status_code == 401 and resposta.json()["codigo"] == "token_invalido"


@pytest.mark.parametrize(
    "variacao",
    [
        {"audiencia": "https://outra-api.teste"},
        {"emissor": "https://outro-logto.teste/oidc"},
    ],
)
def test_audiencia_ou_emissor_errados_sao_recusados(app, emitir, pessoa, variacao):
    # arrange
    token = emitir(str(pessoa["sub"]), **variacao)

    # act
    resposta = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")

    # assert
    assert resposta.status_code == 401 and resposta.json()["codigo"] == "token_invalido"


def test_token_assinado_por_outra_chave_e_recusado(app, pessoa):
    # arrange
    intrusa = ec.generate_private_key(ec.SECP384R1())
    agora = int(time.time())
    token = jwt.encode(
        {
            "sub": str(pessoa["sub"]),
            "iss": "https://logto.teste/oidc",
            "aud": "https://api.teste",
            "exp": agora + 600,
        },
        intrusa,
        algorithm="ES384",
    )

    # act / assert
    resposta = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")
    assert resposta.status_code == 401


def test_algoritmo_none_e_simetrico_nunca_sao_aceitos(app, chave_privada, pessoa):
    # arrange: o ataque clássico: assinar com HS256 usando a chave pública como segredo
    assert "none" not in ALGORITMOS_ACEITOS and "HS256" not in ALGORITMOS_ACEITOS
    agora = int(time.time())
    declaracoes = {
        "sub": str(pessoa["sub"]),
        "iss": "https://logto.teste/oidc",
        "aud": "https://api.teste",
        "exp": agora + 600,
    }
    sem_assinatura = jwt.encode(declaracoes, key="", algorithm="none")
    simetrico = jwt.encode(
        declaracoes, key="segredo-qualquer-com-mais-de-32-bytes!!", algorithm="HS256"
    )

    # act / assert
    for token in (sem_assinatura, simetrico, "lixo.que.nao.e.jwt", "x"):
        resposta = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")
        assert resposta.status_code == 401, token


def test_mensagem_de_token_invalido_nao_distingue_o_motivo(app, emitir, pessoa):
    # arrange
    errado = TestClient(app, headers={"Authorization": f"Bearer {emitir('x', audiencia='z')}"})
    lixo = TestClient(app, headers={"Authorization": "Bearer lixo"})

    # act / assert: não ensina nada a quem tenta adivinhar
    assert errado.get("/formularios").json() == lixo.get("/formularios").json()


def test_sem_logto_configurado_a_api_recusa_todo_pedido_autenticado(dsn, emitir, pessoa):
    # arrange: esquecer de configurar o Logto não pode abrir a API
    configuracao = Configuracao(dsn=dsn, origens_cors=(ORIGEM_PERMITIDA,))
    app = criar_app(configuracao)

    # act
    resposta = TestClient(app, headers={"Authorization": f"Bearer {emitir('x')}"}).get(
        "/formularios"
    )

    # assert
    assert resposta.status_code == 401 and resposta.json()["codigo"] == "autenticacao_indisponivel"


@pytest.mark.parametrize("caminho", ["/healthz", "/legal", "/legal/termos", "/catalogo/permissoes"])
def test_rotas_publicas_nao_pedem_token(app, caminho):
    # act / assert
    assert TestClient(app).get(caminho).status_code == 200


@pytest.mark.parametrize("caminho", ["/catalogo", "/formularios", "/registros/1", "/eu"])
def test_o_token_vale_para_todo_caminho_de_dados(app, caminho):
    # act / assert
    assert TestClient(app).get(caminho).status_code == 401


def test_documentacao_fica_fechada_em_producao(dsn, validador):
    # arrange
    app = criar_app(
        Configuracao(dsn=dsn, origens_cors=(ORIGEM_PERMITIDA,), producao=True), validador=validador
    )
    cliente = TestClient(app)

    # act / assert
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404


# --- equipe, termos e conta ativa ---


def test_pessoa_sem_equipe_recebe_403_pedindo_convite(app, emitir, dsn):
    # arrange: conta nova no Logto, ainda sem convite
    cabecalhos = {"Authorization": f"Bearer {emitir('sub-recem-chegada')}"}

    # act
    resposta = TestClient(app, headers=cabecalhos).get("/formularios")

    # assert
    assert resposta.status_code == 403 and resposta.json()["codigo"] == "sem_equipe"
    assert "convite" in resposta.json()["detalhe"]


def test_o_cabecalho_de_equipe_nao_basta_a_pertenca_e_conferida_no_banco(app, emitir, pessoa, dsn):
    # arrange: outra pessoa, de outra equipe, tenta usar a equipe da primeira
    from conftest import criar_pessoa_na_equipe  # noqa: PLC0415

    intrusa = criar_pessoa_na_equipe(dsn, "intrusa")
    cabecalhos = {
        "Authorization": f"Bearer {emitir(str(intrusa['sub']))}",
        "X-Equipe": str(pessoa["grupo_id"]),
    }

    # act
    resposta = TestClient(app, headers=cabecalhos).get("/formularios")

    # assert
    assert resposta.status_code == 403 and resposta.json()["codigo"] == "sem_equipe"


def test_termos_pendentes_bloqueiam_os_dados_mas_nao_o_eu_nem_o_aceite(app, emitir, dsn):
    # arrange: pessoa nova convidada, sem aceite
    con = abrir_conexao(dsn)
    grupo, admin = servico_equipes.criar_equipe(
        con, "Obra", __import__("datetime").datetime(2026, 11, 2, tzinfo=__import__("datetime").UTC)
    )
    usuario = servico_equipes.identificar(
        con,
        "sub-nova",
        "Nova",
        "n@x.example",
        grupo.criado_em
        and __import__("datetime").datetime(2026, 11, 2, tzinfo=__import__("datetime").UTC),
    )
    con.definir_contexto(Contexto(grupo.id, None))
    servico_equipes.repositorio_equipes.adicionar_membro(
        con,
        grupo.id,
        usuario.id,
        admin.id,
        __import__("datetime").datetime(2026, 11, 2, tzinfo=__import__("datetime").UTC),
    )
    con.close()
    cliente = TestClient(
        app, headers={"Authorization": f"Bearer {emitir('sub-nova')}", "X-Equipe": str(grupo.id)}
    )

    # act
    bloqueado = cliente.get("/formularios")
    eu = cliente.get("/eu")
    aceite = cliente.post("/consentimentos", json={})
    liberado = cliente.get("/formularios")

    # assert
    assert bloqueado.status_code == 403 and bloqueado.json()["codigo"] == "termos_pendentes"
    assert eu.status_code == 200 and sorted(eu.json()["termos_pendentes"]) == [
        "privacidade",
        "termos",
    ]
    assert aceite.status_code == 201 and aceite.json()["pendentes"] == []
    assert liberado.status_code == 200


def test_pessoa_desativada_perde_o_acesso_na_hora(app, cliente, emitir, pessoa, dsn):
    # arrange
    from conftest import criar_pessoa_na_equipe  # noqa: PLC0415

    colega = criar_pessoa_na_equipe(dsn, "colega", "Visualizador", int(pessoa["grupo_id"]))
    do_colega = TestClient(
        app,
        headers={
            "Authorization": f"Bearer {emitir(str(colega['sub']))}",
            "X-Equipe": str(pessoa["grupo_id"]),
        },
    )
    assert do_colega.get("/formularios").status_code == 200

    # act
    desativou = cliente.post(f"/membros/{colega['usuario_id']}/desativar")

    # assert: sem esperar o token expirar, porque o cargo é lido do banco a cada requisição
    assert desativou.status_code == 204
    assert do_colega.get("/formularios").status_code == 403


# --- a matriz de permissões é a tabela única ---


def test_toda_rota_do_app_tem_decisao_na_matriz(app):
    # act / assert: `criar_app` já verifica; aqui o contrato fica explícito
    from forms.api_permissoes import classificar, rotas_do_app  # noqa: PLC0415

    assert [r for r in rotas_do_app(app) if classificar(r) == "negada"] == []


def test_rota_nova_sem_decisao_derruba_a_montagem_do_app(configuracao, validador):
    # arrange
    from fastapi import APIRouter  # noqa: PLC0415

    esquecida = APIRouter()
    esquecida.add_api_route("/rota-esquecida", lambda: None)
    from forms.api_extensoes import Extensao  # noqa: PLC0415

    # act / assert
    with pytest.raises(RuntimeError, match="rota-esquecida"):
        criar_app(configuracao, extensoes=(Extensao("teste", esquecida),), validador=validador)


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
        "Access-Control-Request-Headers": "authorization,x-equipe,content-type",
    }

    # act
    permitida = TestClient(app).options("/formularios", headers=cabecalhos)
    negada = TestClient(app).options(
        "/formularios", headers=cabecalhos | {"Origin": "http://x.example"}
    )

    # assert
    assert permitida.status_code == 200
    assert permitida.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA
    permitidos = permitida.headers["access-control-allow-headers"].lower()
    assert "authorization" in permitidos and "x-equipe" in permitidos
    assert negada.status_code == 400 and "access-control-allow-origin" not in negada.headers


def test_o_401_tambem_leva_os_cabecalhos_cors_para_o_front_conseguir_ler_o_erro(app):
    # act
    resposta = TestClient(app).get("/formularios", headers={"Origin": ORIGEM_PERMITIDA})

    # assert
    assert resposta.status_code == 401
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA


def test_erro_interno_tambem_leva_cors_e_o_formato_uniforme(app, cliente):
    # arrange: uma rota que estoura, como a de qualquer bug do servidor
    def estourar():
        raise RuntimeError("falha inesperada")

    app.add_api_route("/falha-de-teste", estourar)
    sem_erros = TestClient(app, headers=dict(cliente.headers), raise_server_exceptions=False)

    # act
    resposta = sem_erros.get("/falha-de-teste", headers={"Origin": ORIGEM_PERMITIDA})

    # assert: sem o CORS o navegador bloqueia a resposta e o front acha que o servidor caiu
    assert resposta.status_code == 500
    assert resposta.json() == {"detalhe": "Erro interno do servidor.", "erros": []}
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA


def test_cors_nunca_aceita_asterisco(dsn):
    # act / assert
    with pytest.raises(ValueError, match="nunca"):
        Configuracao(dsn=dsn, origens_cors=("*",))


def test_configuracao_do_ambiente_usa_as_duas_origens_do_vite_por_padrao():
    # act
    configuracao = Configuracao.do_ambiente({})

    # assert
    assert configuracao.origens_cors == ("http://localhost:5173", "http://127.0.0.1:5173")
    assert configuracao.logto_endpoint is None and configuracao.producao is False


def test_configuracao_le_o_ambiente():
    # act
    configuracao = Configuracao.do_ambiente(
        {
            "FORMS_DATABASE_URL": "postgresql://u:p@h/b",
            "FORMS_CORS_ORIGINS": "http://a.example, http://b.example",
            "LOGTO_ENDPOINT": "https://auth.exemplo",
            "LOGTO_API_RESOURCE": "https://api.exemplo",
            "FORMS_AMBIENTE": "producao",
            "FORMS_ADMIN_EMAIL": "adm@exemplo.com",
        }
    )

    # assert
    assert configuracao.dsn == "postgresql://u:p@h/b" and configuracao.producao is True
    assert configuracao.origens_cors == ("http://a.example", "http://b.example")
    assert configuracao.logto_endpoint == "https://auth.exemplo"
    assert configuracao.primeiro_administrador == "adm@exemplo.com"


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


def test_erro_inesperado_vira_500_uniforme_sem_vazar_a_causa(cliente, monkeypatch):
    # arrange
    from forms import servico

    def explodir(*argumentos, **nomeados):
        raise RuntimeError("segredo interno /etc/passwd")

    monkeypatch.setattr(servico, "listar_formularios", explodir)
    cliente = TestClient(cliente.app, headers=dict(cliente.headers), raise_server_exceptions=False)

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


# --- corpo limitado, cabeçalhos e limite de taxa (§12) ---


def test_corpo_maior_que_1_mb_e_recusado_com_413_uniforme_e_cors(cliente):
    # arrange
    grande = {"nome": "x", "definicao": {"campos": [], "lixo": "a" * (1024 * 1024 + 10)}}

    # act
    resposta = cliente.post("/formularios", json=grande, headers={"Origin": ORIGEM_PERMITIDA})

    # assert
    assert resposta.status_code == 413
    assert _erro_uniforme(resposta)["detalhe"].startswith("Requisição grande demais")
    assert resposta.headers["access-control-allow-origin"] == ORIGEM_PERMITIDA


def test_corpo_sem_content_length_tambem_e_contado_e_recusado(cliente):
    # arrange: corpo em pedaços (chunked), sem tamanho declarado
    def pedacos():
        for _ in range(20):
            yield b"x" * (100 * 1024)

    # act
    resposta = cliente.post(
        "/formularios", content=pedacos(), headers={"Content-Type": "application/json"}
    )

    # assert
    assert resposta.status_code == 413


def test_corpo_pequeno_passa(cliente):
    # act / assert
    assert (
        cliente.post("/definicoes/validar", json={"definicao": {"campos": []}}).status_code == 200
    )


@pytest.mark.parametrize("caminho", ["/healthz", "/legal", "/formularios", "/rota-que-nao-existe"])
def test_toda_resposta_leva_os_cabecalhos_de_seguranca(cliente, caminho):
    # act
    resposta = cliente.get(caminho)

    # assert
    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert resposta.headers["referrer-policy"] == "no-referrer"
    assert resposta.headers["x-frame-options"] == "DENY"
    assert "geolocation=(self)" in resposta.headers["permissions-policy"]
    assert "camera=()" in resposta.headers["permissions-policy"]
    assert "default-src 'none'" in resposta.headers["content-security-policy"]
    assert resposta.headers["cache-control"] == "no-store"


def test_o_401_tambem_leva_os_cabecalhos_de_seguranca(app):
    # act
    resposta = TestClient(app).get("/formularios")

    # assert
    assert resposta.status_code == 401 and resposta.headers["x-content-type-options"] == "nosniff"


def test_rota_cara_responde_429_com_retry_after_depois_do_limite(cliente, monkeypatch):
    # arrange
    from forms import api_seguranca

    monkeypatch.setitem(
        api_seguranca.LIMITES_POR_ROTA, ("GET", "/busca"), api_seguranca.Limite(2, 60)
    )
    monkeypatch.setattr("forms.api_dependencias.LIMITES_POR_ROTA", api_seguranca.LIMITES_POR_ROTA)

    # act
    respostas = [cliente.get("/busca?q=ab") for _ in range(3)]

    # assert
    assert [r.status_code for r in respostas] == [200, 200, 429]
    assert respostas[2].json()["codigo"] == "limite_excedido"
    assert int(respostas[2].headers["retry-after"]) >= 1
    assert "instantes" in respostas[2].json()["detalhe"]


def test_o_limite_e_por_pessoa_uma_nao_gasta_as_fichas_da_outra(
    app, chave_privada, cliente, pessoa, dsn, monkeypatch
):
    # arrange
    from conftest import cliente_da_pessoa, criar_pessoa_na_equipe
    from forms import api_seguranca

    monkeypatch.setitem(
        api_seguranca.LIMITES_POR_ROTA, ("GET", "/busca"), api_seguranca.Limite(1, 60)
    )
    monkeypatch.setattr("forms.api_dependencias.LIMITES_POR_ROTA", api_seguranca.LIMITES_POR_ROTA)
    outra = cliente_da_pessoa(app, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))

    # act
    assert cliente.get("/busca?q=ab").status_code == 200
    esgotada = cliente.get("/busca?q=ab")
    da_outra = outra.get("/busca?q=ab")

    # assert
    assert esgotada.status_code == 429 and da_outra.status_code == 200


# --- o balde de fichas, sem depender do relógio real ---


def test_balde_deixa_passar_ate_a_capacidade_e_depois_diz_quanto_esperar():
    # arrange
    from forms.api_seguranca import LimitadorDeTaxa, Limite

    agora = [100.0]
    balde = LimitadorDeTaxa(relogio=lambda: agora[0])
    limite = Limite(2, 10)  # 2 pedidos a cada 10 s: uma ficha nova a cada 5 s

    # act
    resultados = [balde.tentar(("p", "r"), limite) for _ in range(3)]

    # assert
    assert resultados[:2] == [None, None] and resultados[2] == pytest.approx(5.0)


def test_balde_repoe_as_fichas_com_o_tempo_mas_nunca_acima_da_capacidade():
    # arrange
    from forms.api_seguranca import LimitadorDeTaxa, Limite

    agora = [0.0]
    balde = LimitadorDeTaxa(relogio=lambda: agora[0])
    limite = Limite(2, 10)
    balde.tentar(("p", "r"), limite)
    balde.tentar(("p", "r"), limite)

    # act
    agora[0] = 5.0
    uma_ficha = balde.tentar(("p", "r"), limite)
    sem_ficha = balde.tentar(("p", "r"), limite)
    agora[0] = 1000.0
    cheio = [balde.tentar(("p", "r"), limite) for _ in range(3)]

    # assert
    assert uma_ficha is None and sem_ficha is not None
    assert cheio[:2] == [None, None] and cheio[2] is not None  # repõe, mas só até 2


def test_baldes_de_chaves_diferentes_sao_independentes():
    # arrange
    from forms.api_seguranca import LimitadorDeTaxa, Limite

    balde = LimitadorDeTaxa(relogio=lambda: 0.0)

    # act / assert
    assert balde.tentar(("a", "r"), Limite(1, 60)) is None
    assert balde.tentar(("a", "r"), Limite(1, 60)) is not None
    assert balde.tentar(("b", "r"), Limite(1, 60)) is None
    assert balde.tentar(("a", "outra-rota"), Limite(1, 60)) is None


# --- registro de acessos sem dado pessoal (AGENTS.md §2.15, §12) ---


def test_log_de_acesso_traz_o_molde_da_rota_e_nunca_o_token_do_convite(cliente, caplog):
    # arrange
    caplog.set_level("INFO", logger="forms.acesso")

    # act
    cliente.post("/convites/TOKEN-SECRETO-DO-CONVITE-123/aceitar")

    # assert
    texto = "\n".join(r.getMessage() for r in caplog.records if r.name == "forms.acesso")
    assert "/convites/{token}/aceitar" in texto
    assert "TOKEN-SECRETO" not in texto


def test_log_de_acesso_nao_guarda_a_query_string_com_o_texto_buscado(cliente, caplog):
    # arrange
    caplog.set_level("INFO", logger="forms.acesso")

    # act
    cliente.get("/busca", params={"q": "maria@exemplo.com"})

    # assert
    texto = "\n".join(r.getMessage() for r in caplog.records if r.name == "forms.acesso")
    assert "/busca" in texto
    assert "maria" not in texto and "exemplo.com" not in texto


def test_resposta_traz_um_identificador_de_requisicao_igual_ao_do_log(cliente, caplog):
    # arrange
    caplog.set_level("INFO", logger="forms.acesso")

    # act
    resposta = cliente.get("/healthz")

    # assert
    identificador = resposta.headers["X-Request-Id"]
    assert identificador
    assert any(f"id={identificador}" in r.getMessage() for r in caplog.records)


def test_rota_inexistente_nao_vaza_o_caminho_no_log(cliente, caplog):
    # arrange
    caplog.set_level("INFO", logger="forms.acesso")

    # act
    cliente.get("/segredo/caminho-que-nao-existe")

    # assert
    texto = "\n".join(r.getMessage() for r in caplog.records if r.name == "forms.acesso")
    assert "caminho-que-nao-existe" not in texto
