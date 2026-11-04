"""Rotas de IA da API (AGENTS.md §2.5): gerador, resumo e assistente de procedimentos.

O LLM é sempre um `ClienteFalso`: nenhum teste faz chamada de rede nem exige chave.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import AGORA, cliente_da_pessoa
from forms.api import Configuracao, criar_app, descobrir_extensoes
from forms.api_dependencias import obter_agora
from forms.ia import extensao as extensao_ia
from forms.ia.cliente import ClienteFalso, IaIndisponivel
from forms.rag import extensao as extensao_rag

DEFINICAO = {"campos": [{"id": "umidade", "tipo": "numero", "rotulo": "Umidade", "unidade": "%"}]}
PROPOSTA = json.dumps({"formularios": [{"nome": "Ensaio", "definicao": DEFINICAO}]})
RESUMO = json.dumps({"titulo": "Visão geral", "paragrafos": ["Há 2 registros."], "destaques": []})


@pytest.fixture
def montar(configuracao, validador, dsn, chave_privada, pessoa):
    """`montar(llm, docs)` -> cliente autenticado com as rotas de IA e o LLM trocado."""

    def construir(llm: ClienteFalso | Exception | None, docs: Path | None):
        return _montar_app(configuracao, validador, dsn, chave_privada, pessoa, llm, docs)

    return construir


def _montar_app(configuracao, validador, dsn, chave_privada, pessoa, llm, docs):
    from forms import banco

    app = criar_app(
        configuracao,
        extensoes=descobrir_extensoes(),
        pool=banco.criar_pool(dsn, tamanho_maximo=4),
        validador=validador,
    )
    app.dependency_overrides[obter_agora] = lambda: AGORA
    if isinstance(llm, Exception):

        def indisponivel():
            raise llm

        app.dependency_overrides[extensao_ia.obter_cliente] = indisponivel
        app.dependency_overrides[extensao_rag.obter_cliente_opcional] = lambda: None
    else:
        app.dependency_overrides[extensao_ia.obter_cliente] = lambda: llm
        app.dependency_overrides[extensao_rag.obter_cliente_opcional] = lambda: llm
    app.dependency_overrides[extensao_rag.obter_pasta_de_docs] = lambda: docs
    return cliente_da_pessoa(app, chave_privada, pessoa)


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    pasta = tmp_path / "docs"
    pasta.mkdir()
    (pasta / "moldagem.md").write_text(
        "# Moldagem\n\n## Cura\n\nManter o concreto úmido por 7 dias.\n", encoding="utf-8"
    )
    return pasta


def _linhas(configuracao: Configuracao) -> tuple[int, int, int]:
    from forms import banco

    conexao = banco.abrir_conexao(configuracao.dsn)
    try:
        return tuple(
            conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]  # noqa: S608
            for tabela in ("formularios", "versoes_formulario", "registros")
        )
    finally:
        conexao.close()


# --- descoberta das extensões ---


def test_extensoes_de_ia_e_rag_sao_descobertas_pelo_nome():
    # act
    nomes = {e.nome for e in descobrir_extensoes()}

    # assert
    assert nomes == {"ia", "rag"}


def test_sem_o_modulo_opcional_o_app_sobe_normalmente():
    # act: módulo inexistente (como se a pasta tivesse sido removida)
    extensoes = descobrir_extensoes(("forms.modulo_que_nao_existe.extensao",))

    # assert
    assert extensoes == ()


def test_erro_dentro_do_modulo_opcional_nao_e_engolido():
    # act / assert: só a AUSÊNCIA do módulo é aceita; um bug nele tem de aparecer
    with pytest.raises(ModuleNotFoundError, match="dependencia_que_falta"):
        descobrir_extensoes(("extensao_quebrada",))


def test_app_sem_extensoes_nao_tem_as_rotas_de_ia(app, cliente):
    # arrange: o `app` das fixtures não carrega as extensões

    # act
    gerar = cliente.post("/definicoes/gerar", json={"pedido": "x"})

    # assert
    assert gerar.status_code == 404
    assert cliente.get("/formularios").status_code == 200


def test_rotas_de_ia_exigem_o_token(configuracao, validador, dsn):
    # arrange
    from forms import banco

    app = criar_app(
        configuracao,
        extensoes=descobrir_extensoes(),
        pool=banco.criar_pool(dsn, tamanho_maximo=2),
        validador=validador,
    )
    sem_token = TestClient(app)

    # act / assert
    assert sem_token.post("/definicoes/gerar", json={"pedido": "x"}).status_code == 401
    assert sem_token.post("/assistente/perguntar", json={"pergunta": "x"}).status_code == 401
    assert sem_token.post("/formularios/1/resumo").status_code == 401


# --- POST /definicoes/gerar ---


def test_gerar_devolve_o_rascunho_sem_criar_nada(montar, configuracao, docs):
    # arrange
    cliente = montar(ClienteFalso([PROPOSTA]), docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "um ensaio de umidade"})

    # assert
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {
        "formularios": [{"nome": "Ensaio", "definicao": DEFINICAO, "erros": []}]
    }
    assert _linhas(configuracao) == (0, 0, 0)  # nunca salva


def test_gerar_devolve_os_erros_de_cada_rascunho_para_a_pessoa_corrigir(montar, configuracao, docs):
    # arrange: a IA insiste numa fórmula proibida nas três voltas
    invalida = json.dumps(
        {
            "formularios": [
                {
                    "nome": "Ensaio",
                    "definicao": {
                        "campos": [
                            {"id": "x", "tipo": "calculado", "rotulo": "X", "formula": "abs(1)"}
                        ]
                    },
                }
            ]
        }
    )
    cliente = montar(ClienteFalso([invalida] * 3), docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "um ensaio"})

    # assert
    assert resposta.status_code == 200
    (rascunho,) = resposta.json()["formularios"]
    assert rascunho["erros"] and rascunho["erros"][0]["campo"] == "x.formula"


def test_gerar_aceita_os_rascunhos_em_edicao_para_refinar(montar, configuracao, docs):
    # arrange
    llm = ClienteFalso([PROPOSTA])
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post(
        "/definicoes/gerar",
        json={
            "pedido": "adicione um campo",
            "rascunhos": [{"nome": "Ensaio", "definicao": DEFINICAO}],
        },
    )

    # assert: os rascunhos chegam ao prompt
    assert resposta.status_code == 200
    assert "Umidade" in llm.chamadas[0][1] or "umidade" in llm.chamadas[0][1]


def test_gerar_sem_chave_ou_internet_responde_503_em_portugues(montar, configuracao, docs):
    # arrange
    cliente = montar(IaIndisponivel("Defina ANTHROPIC_API_KEY no .env."), docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "um ensaio"})

    # assert: formato uniforme, e o construtor manual segue funcionando
    assert resposta.status_code == 503
    assert resposta.json() == {"detalhe": "Defina ANTHROPIC_API_KEY no .env.", "erros": []}
    assert cliente.get("/formularios").status_code == 200


def test_gerar_com_resposta_fora_do_formato_responde_502(montar, configuracao, docs):
    # arrange
    cliente = montar(ClienteFalso(["isto não é JSON"] * 3), docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "um ensaio"})

    # assert
    assert resposta.status_code == 502
    assert "IA" in resposta.json()["detalhe"]


@pytest.mark.parametrize("pedido", ["", "   "])
def test_gerar_com_pedido_vazio_responde_422(montar, configuracao, docs, pedido):
    # arrange
    llm = ClienteFalso([])
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": pedido})

    # assert: nem chega ao LLM
    assert resposta.status_code == 422
    assert llm.chamadas == []


def test_gerar_com_pedido_enorme_responde_422_sem_chamar_o_llm(montar, configuracao, docs):
    # arrange
    llm = ClienteFalso([])
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "a" * 100_000})

    # assert
    assert resposta.status_code == 422
    assert resposta.json()["erros"][0]["campo"] == "pedido"
    assert llm.chamadas == []


def test_gerar_recusa_campo_desconhecido(montar, configuracao, docs):
    # arrange
    cliente = montar(ClienteFalso([]), docs)

    # act
    resposta = cliente.post("/definicoes/gerar", json={"pedido": "x", "salvar": True})

    # assert
    assert resposta.status_code == 422


# --- POST /formularios/{id}/resumo ---


def _formulario_com_registros(cliente: TestClient) -> int:
    criado = cliente.post("/formularios", json={"nome": "Ensaio", "definicao": DEFINICAO}).json()
    versao = criado["versao_atual"]["id"]
    for valor in ("10", "20"):
        cliente.post(
            f"/formularios/{criado['id']}/registros",
            json={"versao_id": versao, "dados": {"umidade": valor}},
        )
    return criado["id"]


def test_resumo_devolve_o_texto_conferido_e_o_total(montar, configuracao, docs):
    # arrange
    cliente = montar(ClienteFalso([RESUMO]), docs)
    formulario_id = _formulario_com_registros(cliente)

    # act
    resposta = cliente.post(f"/formularios/{formulario_id}/resumo")

    # assert
    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {
        "titulo": "Visão geral",
        "paragrafos": ["Há 2 registros."],
        "destaques": [],
        "total": 2,
    }


def test_resumo_com_numero_que_nao_bate_com_o_banco_responde_502(montar, configuracao, docs):
    # arrange: o LLM inventa "3 registros"
    mentira = json.dumps({"titulo": "T", "paragrafos": ["Há 3 registros."], "destaques": []})
    cliente = montar(ClienteFalso([mentira]), docs)
    formulario_id = _formulario_com_registros(cliente)

    # act
    resposta = cliente.post(f"/formularios/{formulario_id}/resumo")

    # assert
    assert resposta.status_code == 502
    assert "não confere" in resposta.json()["detalhe"]


def test_resumo_so_envia_agregados_ao_llm_e_nao_grava_nada(montar, configuracao, docs):
    # arrange
    llm = ClienteFalso([RESUMO])
    cliente = montar(llm, docs)
    formulario_id = _formulario_com_registros(cliente)
    antes = _linhas(configuracao)

    # act
    cliente.post(f"/formularios/{formulario_id}/resumo")

    # assert
    assert _linhas(configuracao) == antes
    assert "<agregados>" in llm.chamadas[0][1]


def test_resumo_respeita_os_filtros_da_listagem(montar, configuracao, docs):
    # arrange: só um dos dois registros passa no filtro de data (todos criados em AGORA)
    cliente = montar(ClienteFalso([]), docs)
    formulario_id = _formulario_com_registros(cliente)

    # act
    resposta = cliente.post(f"/formularios/{formulario_id}/resumo?criado_de=2030-01-01")

    # assert: nada para resumir -> 422, sem chamar o LLM
    assert resposta.status_code == 422
    assert "registros" in resposta.json()["detalhe"]


def test_resumo_de_formulario_inexistente_responde_404(montar, configuracao, docs):
    # arrange
    cliente = montar(ClienteFalso([]), docs)

    # act / assert
    assert cliente.post("/formularios/999/resumo").status_code == 404


def test_resumo_sem_ia_responde_503(montar, configuracao, docs):
    # arrange
    cliente = montar(IaIndisponivel("Sem chave."), docs)
    formulario_id = _formulario_com_registros(cliente)

    # act
    resposta = cliente.post(f"/formularios/{formulario_id}/resumo")

    # assert
    assert resposta.status_code == 503


# --- POST /assistente/perguntar ---


def test_perguntar_responde_com_o_trecho_e_o_arquivo_de_origem(montar, configuracao, docs):
    # arrange
    llm = ClienteFalso(["Mantenha úmido por 7 dias (moldagem.md)."])
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post("/assistente/perguntar", json={"pergunta": "quantos dias de cura?"})

    # assert
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["encontrou"] is True and corpo["usou_ia"] is True
    assert corpo["texto"] == "Mantenha úmido por 7 dias (moldagem.md)."
    assert corpo["trechos"][0]["arquivo"] == "moldagem.md"
    assert corpo["trechos"][0]["titulo"] == "Moldagem > Cura"
    assert "7 dias" in corpo["trechos"][0]["texto"]


def test_perguntar_sem_base_nos_documentos_diz_que_nao_encontrou(montar, configuracao, docs):
    # arrange
    llm = ClienteFalso([])
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post("/assistente/perguntar", json={"pergunta": "receita de bolo"})

    # assert
    assert resposta.status_code == 200
    assert resposta.json() == {
        "encontrou": False,
        "texto": "Não encontrei isso nos procedimentos.",
        "usou_ia": False,
        "trechos": [],
    }
    assert llm.chamadas == []


def test_perguntar_sem_ia_mostra_so_os_trechos_e_nao_da_erro(montar, configuracao, docs):
    # arrange: sem chave ou internet, o RAG degrada para os trechos (fallback)
    cliente = montar(IaIndisponivel("Sem chave."), docs)

    # act
    resposta = cliente.post("/assistente/perguntar", json={"pergunta": "quantos dias de cura?"})

    # assert
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["encontrou"] is True and corpo["texto"] is None and corpo["usou_ia"] is False
    assert corpo["trechos"][0]["arquivo"] == "moldagem.md"


def test_perguntar_sem_pasta_de_documentos_diz_que_nao_encontrou(montar, configuracao):
    # arrange
    cliente = montar(ClienteFalso([]), None)

    # act
    resposta = cliente.post("/assistente/perguntar", json={"pergunta": "cura"})

    # assert
    assert resposta.status_code == 200 and resposta.json()["encontrou"] is False


@pytest.mark.parametrize("pergunta", ["", "a" * 5000])
def test_perguntar_valida_o_tamanho_da_pergunta(montar, configuracao, docs, pergunta):
    # arrange
    cliente = montar(ClienteFalso([]), docs)

    # act / assert
    assert cliente.post("/assistente/perguntar", json={"pergunta": pergunta}).status_code == 422


def test_perguntar_usa_a_busca_hibrida_quando_ha_provedor_de_embeddings(montar, configuracao, docs):
    # arrange: nenhuma palavra da pergunta aparece nos documentos; só o significado liga os dois
    trecho = "Moldagem > Cura\nManter o concreto úmido por 7 dias."
    llm = ClienteFalso(
        ["Mantenha úmido por 7 dias."],
        vetores={trecho: [1.0, 0.0], "irrigar a massa fresca": [0.9, 0.1]},
        modelo_de_vetores="falso-1",
    )
    cliente = montar(llm, docs)

    # act
    resposta = cliente.post("/assistente/perguntar", json={"pergunta": "irrigar a massa fresca"})

    # assert
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["encontrou"] is True
    assert resposta.json()["trechos"][0]["arquivo"] == "moldagem.md"
