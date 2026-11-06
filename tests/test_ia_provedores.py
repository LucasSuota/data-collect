"""Provedores de LLM: o adaptador compatível com OpenAI e a configuração por equipe
(AGENTS.md §2.5, §2.15, §12). Nenhum teste toca a rede: o transporte do `httpx` é falso."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from forms.ia import configuracao, repositorio
from forms.ia.cliente import (
    ClienteAnthropic,
    ClienteFalso,
    ClienteOpenAICompativel,
    IaIndisponivel,
    validar_base_url,
)
from forms.infra.banco import Conexao
from forms.infra.segredos import Cifra, nova_chave_mestra

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)


def _cliente(rotas, **opcoes) -> ClienteOpenAICompativel:
    http = httpx.Client(transport=httpx.MockTransport(rotas))
    return ClienteOpenAICompativel(
        opcoes.pop("base_url", "http://localhost:11434/v1/"),
        opcoes.pop("chave", "sk-segredo"),
        opcoes.pop("modelo", "llama3"),
        cliente_http=http,
        **opcoes,
    )


# --- adaptador compatível com OpenAI ---


def test_completar_envia_o_formato_chat_completions_e_devolve_o_texto():
    # arrange
    vistos = []

    def rotas(pedido: httpx.Request) -> httpx.Response:
        vistos.append(
            (pedido.url.path, pedido.headers.get("authorization"), json.loads(pedido.content))
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": "olá!"}}]})

    # act
    texto = _cliente(rotas).completar("Seja breve.", "Oi", maximo_de_tokens=50)

    # assert
    caminho, autorizacao, corpo = vistos[0]
    assert texto == "olá!" and caminho == "/v1/chat/completions"
    assert autorizacao == "Bearer sk-segredo"
    assert corpo["model"] == "llama3" and corpo["max_tokens"] == 50 and corpo["temperature"] == 0
    assert corpo["messages"] == [
        {"role": "system", "content": "Seja breve."},
        {"role": "user", "content": "Oi"},
    ]


def test_sem_chave_nao_manda_authorization_como_no_ollama_local():
    # arrange
    vistos = []

    def rotas(pedido: httpx.Request) -> httpx.Response:
        vistos.append(pedido.headers.get("authorization"))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    # act
    _cliente(rotas, chave=None).completar("s", "m", maximo_de_tokens=5)

    # assert
    assert vistos == [None]


def test_fluxo_junta_os_pedacos_do_sse_e_para_no_done():
    # arrange
    sse = (
        'data: {"choices":[{"delta":{"content":"Ol"}}]}\n\n'
        'data: {"choices":[{"delta":{}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"á"}}]}\n\n'
        "data: [DONE]\n\n"
        'data: {"choices":[{"delta":{"content":"NUNCA"}}]}\n\n'
    )
    cliente = _cliente(lambda p: httpx.Response(200, content=sse.encode()))

    # act
    pedacos = list(cliente.completar_em_fluxo("s", "m", maximo_de_tokens=10))

    # assert
    assert pedacos == ["Ol", "á"]


def test_vetorizar_devolve_na_ordem_do_indice_mesmo_se_o_provedor_embaralhar():
    # arrange
    def rotas(pedido: httpx.Request) -> httpx.Response:
        assert json.loads(pedido.content)["model"] == "nomic-embed"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    cliente = _cliente(rotas, modelo_de_vetores="nomic-embed")

    # act / assert
    assert cliente.vetorizar(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert cliente.capacidades.embeddings is True and cliente.modelo_de_vetores == "nomic-embed"


def test_sem_modelo_de_embeddings_a_busca_semantica_fica_indisponivel():
    # arrange
    cliente = _cliente(lambda p: httpx.Response(200, json={}))

    # act / assert
    assert cliente.capacidades.embeddings is False
    with pytest.raises(IaIndisponivel, match="embeddings"):
        cliente.vetorizar(["x"])


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(401, json={"error": "chave sk-segredo inválida"}),
        httpx.Response(500),
        httpx.Response(200, json={"sem": "choices"}),
        httpx.Response(200, content=b"nao e json"),
    ],
)
def test_falha_do_provedor_vira_ia_indisponivel_sem_vazar_a_chave(resposta):
    # arrange
    cliente = _cliente(lambda p: resposta)

    # act
    with pytest.raises(IaIndisponivel) as erro:
        cliente.completar("s", "m", maximo_de_tokens=5)

    # assert
    assert "sk-segredo" not in str(erro.value) and "sk-segredo" not in repr(cliente)
    assert "O restante do aplicativo continua funcionando" in str(erro.value)


def test_falha_de_rede_vira_ia_indisponivel():
    # arrange
    def sem_rede(pedido: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem internet")

    # act / assert
    with pytest.raises(IaIndisponivel):
        _cliente(sem_rede).completar("s", "m", maximo_de_tokens=5)


@pytest.mark.parametrize(
    "endereco",
    ["", "ftp://x.io", "localhost:11434", "file:///etc/passwd", "http://usuario:senha@x.io/v1"],
)
def test_endereco_do_provedor_invalido_e_recusado(endereco):
    # act / assert
    with pytest.raises(IaIndisponivel):
        validar_base_url(endereco)


def test_endereco_valido_perde_a_barra_final():
    # act / assert
    assert validar_base_url(" https://api.openai.com/v1/ ") == "https://api.openai.com/v1"


# --- configuração por equipe ---


@pytest.fixture
def cifra() -> Cifra:
    return Cifra([nova_chave_mestra()])


def _ligar(conexao: Conexao, cifra: Cifra | None, **mudancas):
    argumentos = {
        "ativa": True,
        "aceite_do_aviso": True,
        "provedor": "openai_compativel",
        "base_url": "http://localhost:11434/v1",
        "modelo": "llama3",
        "modelo_embeddings": None,
        "chave": None,
        "agora": AGORA,
    } | mudancas
    return configuracao.atualizar(conexao, cifra, **argumentos)


def test_ia_nasce_desligada_e_sem_chave(conexao: Conexao):
    # act
    config = configuracao.obter(conexao)

    # assert
    assert (config.ativa, config.chave_definida) == (False, False)


def test_ligar_exige_o_aceite_do_aviso_e_registra_quem_aceitou(conexao: Conexao, cifra):
    # act / assert
    with pytest.raises(configuracao.ConfigInvalida) as erro:
        _ligar(conexao, cifra, aceite_do_aviso=False)
    assert erro.value.erros[0].campo == "aceite_do_aviso"
    config = _ligar(conexao, cifra)
    assert config.ativa and config.consentimento_por == conexao.usuario_id
    assert config.consentimento_em == "2026-11-02T10:00:00+00:00"


def test_a_chave_vai_cifrada_ao_banco_e_nunca_volta_pela_configuracao(conexao: Conexao, cifra):
    # act
    config = _ligar(conexao, cifra, chave="sk-minha-chave")
    bruto = repositorio.obter_config(conexao).chave_cifrada

    # assert
    assert config.chave_definida is True
    assert bruto != "sk-minha-chave" and "sk-minha" not in bruto
    assert cifra.decifrar(bruto) == "sk-minha-chave"
    assert "sk-minha-chave" not in repr(config) and not hasattr(config, "chave")
    dump = [dict(linha) for linha in conexao.execute("SELECT * FROM config_ia_grupo")]
    assert "sk-minha-chave" not in str(dump)


def test_chave_omitida_mantem_vazia_remove_e_nova_troca(conexao: Conexao, cifra):
    # arrange
    _ligar(conexao, cifra, chave="sk-1")

    # act / assert
    assert _ligar(conexao, cifra, chave=None).chave_definida is True
    assert cifra.decifrar(repositorio.obter_config(conexao).chave_cifrada) == "sk-1"
    _ligar(conexao, cifra, chave="sk-2")
    assert cifra.decifrar(repositorio.obter_config(conexao).chave_cifrada) == "sk-2"
    assert _ligar(conexao, cifra, chave="").chave_definida is False


def test_sem_chave_mestra_no_servidor_a_chave_nao_e_aceita_em_claro(conexao: Conexao):
    # act / assert
    with pytest.raises(Exception, match="chave-mestra"):
        _ligar(conexao, None, chave="sk-1")
    assert (
        repositorio.obter_config(conexao) is None
        or repositorio.obter_config(conexao).chave_cifrada is None
    )


@pytest.mark.parametrize(
    ("mudancas", "campo"),
    [
        ({"provedor": "inventado"}, "provedor"),
        ({"base_url": "ftp://x"}, "base_url"),
        ({"base_url": None}, "base_url"),
    ],
)
def test_configuracao_invalida_e_recusada_com_o_campo(conexao: Conexao, cifra, mudancas, campo):
    # act / assert
    with pytest.raises(configuracao.ConfigInvalida) as erro:
        _ligar(conexao, cifra, **mudancas)
    assert campo in {e.campo for e in erro.value.erros}


def test_desligar_nao_pede_o_aceite_de_novo_e_religar_so_pede_se_estava_desligada(
    conexao: Conexao, cifra
):
    # arrange
    _ligar(conexao, cifra)

    # act
    desligada = _ligar(conexao, cifra, ativa=False, aceite_do_aviso=False)
    alterada_ligada = _ligar(conexao, cifra, ativa=True, aceite_do_aviso=True)

    # assert
    assert desligada.ativa is False and alterada_ligada.ativa is True


def test_ia_desligada_na_equipe_nunca_cria_cliente_mesmo_com_chave_da_instancia(
    conexao: Conexao, cifra
):
    # arrange
    ambiente = {"ANTHROPIC_API_KEY": "sk-da-instancia"}

    # act / assert: sem o aceite da equipe, nada é enviado (§2.15)
    with pytest.raises(IaIndisponivel, match="desligada"):
        configuracao.criar_cliente_da_equipe(conexao, cifra, ambiente)


def test_cliente_da_equipe_usa_o_provedor_configurado(conexao: Conexao, cifra):
    # arrange
    _ligar(conexao, cifra, chave="sk-x", modelo_embeddings="embed-1")

    # act
    cliente = configuracao.criar_cliente_da_equipe(conexao, cifra, {})

    # assert
    assert isinstance(cliente, ClienteOpenAICompativel)
    assert cliente.modelo == "llama3" and cliente.modelo_de_vetores == "embed-1"


def test_anthropic_da_equipe_usa_a_chave_dela(conexao: Conexao, cifra):
    # arrange
    _ligar(conexao, cifra, provedor="anthropic", base_url=None, modelo=None, chave="sk-ant")

    # act / assert
    assert isinstance(configuracao.criar_cliente_da_equipe(conexao, cifra, {}), ClienteAnthropic)


def test_equipe_ligada_sem_provedor_proprio_usa_o_padrao_da_instancia(conexao: Conexao, cifra):
    # arrange
    _ligar(conexao, cifra, provedor="anthropic", base_url=None, modelo=None, chave=None)

    # act
    cliente = configuracao.criar_cliente_da_equipe(conexao, cifra, {"ANTHROPIC_API_KEY": "sk-i"})

    # assert
    assert isinstance(cliente, ClienteAnthropic)
    with pytest.raises(IaIndisponivel):
        configuracao.criar_cliente_da_equipe(conexao, cifra, {})


def test_chave_ilegivel_pede_para_cadastrar_de_novo_em_vez_de_quebrar(conexao: Conexao, cifra):
    # arrange
    _ligar(conexao, cifra, chave="sk-1")
    outra_cifra = Cifra([nova_chave_mestra()])  # a chave-mestra foi trocada sem rotação

    # act / assert
    with pytest.raises(IaIndisponivel, match="Cadastre a chave de novo"):
        configuracao.criar_cliente_da_equipe(conexao, outra_cifra, {})


def test_configuracao_de_uma_equipe_nao_aparece_na_outra(
    conexao: Conexao, outra_equipe: Conexao, cifra
):
    # arrange
    _ligar(conexao, cifra, chave="sk-da-a")

    # act / assert
    assert configuracao.obter(outra_equipe).ativa is False
    assert repositorio.obter_config(outra_equipe) is None


def test_cliente_falso_tambem_serve_ao_fluxo():
    # act / assert
    assert (
        "".join(
            ClienteFalso(["resposta longa para o fluxo"]).completar_em_fluxo(
                "s", "m", maximo_de_tokens=1
            )
        )
        == "resposta longa para o fluxo"
    )
