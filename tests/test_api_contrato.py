"""O contrato com o `frontend/` (AGENTS.md §5.3): renomear ou remover campo de resposta, ou
mudar o conjunto de rotas, faz um destes testes falhar. Mudança incompatível exige sinalizar."""

import json
from pathlib import Path

import pytest

from forms.api import app as app_real
from forms.exportar_openapi import main as exportar

# Campos de cada modelo de resposta: nome -> obrigatório. É o JSON esperado pelo front.
MODELOS_DE_RESPOSTA = {
    "ErroSaida": {"detalhe": True, "erros": False},
    "ErroDeCampoSaida": {"campo": True, "mensagem": True, "posicao": False},
    "PosicaoSaida": {"inicio": True, "fim": True},
    "ResumoDeFormularioSaida": {
        "id": True,
        "nome": True,
        "criado_em": True,
        "versao_atual_id": True,
        "versao_atual_numero": True,
    },
    "CampoSaida": {
        "id": True,
        "tipo": True,
        "rotulo": True,
        "obrigatorio": False,
        "unidade": False,
        "casas_decimais": False,
        "opcoes": False,
        "formula": False,
        "formulario": False,
        "compartilhado": False,
        "maximo": False,
    },
    "DefinicaoSaida": {"campos": True},
    "VersaoSaida": {
        "id": True,
        "formulario_id": True,
        "numero": True,
        "definicao": True,
        "publicada_em": True,
    },
    "ResumoDeVersaoSaida": {"id": True, "numero": True, "publicada_em": True},
    "FormularioDetalheSaida": {"id": True, "nome": True, "criado_em": True, "versao_atual": True},
    "ValidarSaida": {"valida": True, "erros": True},
    "PreviaSaida": {"valida": True, "erros": True, "calculados": True},
    "ResultadoCalculadoSaida": {"valor": True, "erro": True},
    "CatalogoSaida": {"tipos": True, "funcoes": True, "constantes": True, "nomes_reservados": True},
    "TipoDoCatalogoSaida": {"id": True, "rotulo": True, "propriedades": True},
    "FuncaoDoCatalogoSaida": {"nome": True, "assinatura": True, "descricao": True, "exemplo": True},
    "ConstanteDoCatalogoSaida": {"nome": True, "valor": True, "tipo": True, "descricao": True},
    "RegistroSaida": {
        "id": True,
        "formulario_id": True,
        "versao_id": True,
        "dados": True,
        "criado_em": True,
        "atualizado_em": True,
    },
    "ColunaSaida": {
        "id": True,
        "rotulo": True,
        "unidade": True,
        "tipo": True,
        "casas_decimais": True,
        "resultado": True,
        "opcoes": True,
        "filtravel": True,
    },
    "ListagemDeRegistrosSaida": {"versao_id": True, "colunas": True, "itens": True, "total": True},
    "AnexoSaida": {"id": True, "largura": True, "altura": True, "tamanho_bytes": True},
    # extensões opcionais (ia/ e rag/): fazem parte do contrato quando o módulo existe
    "RascunhoGeradoSaida": {"nome": True, "definicao": True, "erros": True},
    "GerarSaida": {"formularios": True},
    "ResumoSaida": {"titulo": True, "paragrafos": True, "destaques": True, "total": True},
    "TrechoSaida": {"arquivo": True, "titulo": True, "texto": True, "pontuacao": True},
    "RespostaSaida": {"encontrou": True, "texto": True, "usou_ia": True, "trechos": True},
}

MODELOS_DE_ENTRADA = {
    "FormularioEntrada": {"nome": True, "definicao": True},
    "LoteEntrada": {"formularios": True},
    "VersaoEntrada": {"definicao": True},
    "ValidarEntrada": {"definicao": True},
    "PreviaEntrada": {"definicao": True, "valores": False},
    "RegistroEntrada": {"versao_id": True, "dados": True},
    "RegistroAtualizacao": {"dados": True},
    "GerarEntrada": {"pedido": True, "rascunhos": False},
    "PerguntaEntrada": {"pergunta": True},
}

ROTAS = [
    ("delete", "/formularios/{formulario_id}"),
    ("delete", "/registros/{registro_id}"),
    ("get", "/anexos/{anexo_id}"),
    ("get", "/catalogo"),
    ("get", "/formularios"),
    ("get", "/formularios/{formulario_id}"),
    ("get", "/formularios/{formulario_id}/registros"),
    ("get", "/formularios/{formulario_id}/registros/exportar"),
    ("get", "/formularios/{formulario_id}/versoes"),
    ("get", "/formularios/{formulario_id}/versoes/{versao_id}"),
    ("get", "/registros/{registro_id}"),
    ("post", "/anexos"),
    ("post", "/assistente/perguntar"),
    ("post", "/definicoes/gerar"),
    ("post", "/definicoes/previa"),
    ("post", "/definicoes/validar"),
    ("post", "/formularios"),
    ("post", "/formularios/lote"),
    ("post", "/formularios/{formulario_id}/registros"),
    ("post", "/formularios/{formulario_id}/resumo"),
    ("post", "/formularios/{formulario_id}/versoes"),
    ("put", "/registros/{registro_id}"),
]

# Respostas que não são JSON de modelo: 204 sem corpo, CSV e imagem.
SEM_MODELO = {
    ("delete", "/formularios/{formulario_id}"),
    ("delete", "/registros/{registro_id}"),
    ("get", "/anexos/{anexo_id}"),
    ("get", "/formularios/{formulario_id}/registros/exportar"),
}


@pytest.fixture(scope="module")
def openapi() -> dict:
    return app_real.openapi()


def _campos(openapi: dict, modelo: str) -> dict[str, bool]:
    esquema = openapi["components"]["schemas"][modelo]
    obrigatorios = set(esquema.get("required", []))
    return {nome: nome in obrigatorios for nome in esquema["properties"]}


@pytest.mark.parametrize("modelo", sorted(MODELOS_DE_RESPOSTA))
def test_campos_de_cada_modelo_de_resposta_nao_mudaram_sem_querer(openapi, modelo):
    # act / assert: nomes e obrigatoriedade, um modelo por teste
    assert _campos(openapi, modelo) == MODELOS_DE_RESPOSTA[modelo]


@pytest.mark.parametrize("modelo", sorted(MODELOS_DE_ENTRADA))
def test_campos_de_cada_modelo_de_entrada_nao_mudaram_sem_querer(openapi, modelo):
    # act / assert
    assert _campos(openapi, modelo) == MODELOS_DE_ENTRADA[modelo]


def test_nao_ha_modelo_no_openapi_fora_do_contrato_conhecido(openapi):
    # arrange
    conhecidos = set(MODELOS_DE_RESPOSTA) | set(MODELOS_DE_ENTRADA)
    pydantic = {"HTTPValidationError", "ValidationError", "Body_enviar_anexo_anexos_post"}

    # act / assert: modelo novo precisa entrar neste arquivo, de propósito
    assert set(openapi["components"]["schemas"]) - conhecidos - pydantic == set()


def test_conjunto_de_rotas_do_contrato(openapi):
    # act
    encontradas = sorted(
        (metodo, caminho) for caminho, operacoes in openapi["paths"].items() for metodo in operacoes
    )

    # assert
    assert encontradas == sorted(ROTAS)


def test_nao_existe_put_patch_nem_delete_de_versao_e_nem_patch_de_registro(openapi):
    # assert
    versoes = openapi["paths"]["/formularios/{formulario_id}/versoes/{versao_id}"]
    assert set(versoes) == {"get"}
    assert set(openapi["paths"]["/registros/{registro_id}"]) == {"get", "put", "delete"}


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS)
def test_todo_endpoint_tem_resposta_de_sucesso_com_modelo_explicito(openapi, metodo, caminho):
    # arrange
    operacao = openapi["paths"][caminho][metodo]
    sucesso = next(r for codigo, r in operacao["responses"].items() if codigo.startswith("2"))

    # assert
    if (metodo, caminho) in SEM_MODELO:
        return  # 204, CSV e imagem: declarados por `response_class`/`responses`, sem modelo JSON
    esquema = sucesso["content"]["application/json"]["schema"]
    assert "$ref" in esquema or esquema.get("items", {}).get("$ref"), operacao["summary"]


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS)
def test_todo_endpoint_documenta_o_erro_uniforme_para_401_404_e_422(openapi, metodo, caminho):
    # arrange
    respostas = openapi["paths"][caminho][metodo]["responses"]

    # assert
    for codigo in ("401", "404", "422"):
        esquema = respostas[codigo]["content"]["application/json"]["schema"]
        assert esquema["$ref"].endswith("/ErroSaida"), (codigo, caminho)


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [("delete", "/formularios/{formulario_id}"), ("delete", "/registros/{registro_id}")],
)
def test_exclusoes_documentam_o_409(openapi, metodo, caminho):
    # act / assert
    assert openapi["paths"][caminho][metodo]["responses"]["409"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/ErroSaida")


def test_a_autenticacao_por_token_esta_no_openapi(openapi):
    # assert
    esquema = openapi["components"]["securitySchemes"]["TokenDaExecucao"]
    assert esquema == {"type": "apiKey", "in": "header", "name": "X-Forms-Token"}


def test_o_filtro_por_campo_esta_documentado_na_listagem(openapi):
    # arrange
    parametros = openapi["paths"]["/formularios/{formulario_id}/registros"]["get"]["parameters"]

    # act / assert
    nomes = {p["name"] for p in parametros}
    assert nomes == {
        "formulario_id",
        "versao_id",
        "limite",
        "deslocamento",
        "criado_de",
        "criado_ate",
        "filtro",
    }
    limite = next(p for p in parametros if p["name"] == "limite")["schema"]
    assert (limite["default"], limite["minimum"], limite["maximum"]) == (50, 1, 200)


def test_o_prefixo_de_erro_do_lote_esta_documentado(openapi):
    # act
    descricao = openapi["paths"]["/formularios/lote"]["post"]["description"]

    # assert
    assert "prefixo" in descricao and "proctor.umidade.formula" in descricao


# --- erros reais com o formato uniforme: 404, 409 e 422 ---


def test_404_409_e_422_seguem_o_formato_uniforme(cliente):
    # arrange
    criado = cliente.post("/formularios", json={"nome": "f", "definicao": {"campos": []}}).json()
    cliente.post(
        f"/formularios/{criado['id']}/registros",
        json={"versao_id": criado["versao_atual"]["id"], "dados": {}},
    )

    # act
    respostas = {
        404: cliente.get("/registros/999"),
        409: cliente.delete(f"/formularios/{criado['id']}"),
        422: cliente.post("/formularios", json={"nome": "g", "definicao": 1}),
    }

    # assert
    for codigo, resposta in respostas.items():
        assert resposta.status_code == codigo
        assert set(resposta.json()) == {"detalhe", "erros"}


# --- exportação do openapi.json ---


def test_exportar_grava_o_mesmo_openapi_do_app(tmp_path):
    # arrange
    destino = tmp_path / "openapi.json"

    # act
    codigo = exportar(["--saida", str(destino)])

    # assert
    assert codigo == 0
    assert json.loads(destino.read_text(encoding="utf-8")) == app_real.openapi()
    assert destino.read_text(encoding="utf-8").endswith("}\n")


def test_exportar_e_deterministico(tmp_path):
    # act
    exportar(["--saida", str(tmp_path / "a.json")])
    exportar(["--saida", str(tmp_path / "b.json")])

    # assert
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


def test_conferir_passa_quando_o_arquivo_esta_em_dia_e_falha_quando_desatualizado(tmp_path, capsys):
    # arrange
    arquivo = tmp_path / "openapi.json"
    exportar(["--saida", str(arquivo)])

    # act / assert
    assert exportar(["--saida", str(arquivo), "--conferir"]) == 0
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace('"0.1.0"', '"9.9.9"'), encoding="utf-8"
    )
    assert exportar(["--saida", str(arquivo), "--conferir"]) == 1
    assert "desatualizado" in capsys.readouterr().err


def test_conferir_arquivo_inexistente_falha(tmp_path, capsys):
    # act
    codigo = exportar(["--saida", str(tmp_path / "nada.json"), "--conferir"])

    # assert
    assert codigo == 1 and "desatualizado" in capsys.readouterr().err


def test_o_openapi_nao_muda_dependendo_de_quem_importa(tmp_path):
    # act: a exportação não pode depender de variáveis de ambiente nem de banco
    exportar(["--saida", str(tmp_path / "x.json")])

    # assert
    assert not list(Path(tmp_path).glob("*.db"))


@pytest.mark.parametrize(
    ("caminho", "codigos"),
    [
        ("/definicoes/gerar", ("502", "503")),
        ("/formularios/{formulario_id}/resumo", ("502", "503")),
    ],
)
def test_rotas_de_ia_documentam_o_502_e_o_503_com_o_erro_uniforme(openapi, caminho, codigos):
    # arrange
    respostas = openapi["paths"][caminho]["post"]["responses"]

    # assert
    for codigo in codigos:
        assert respostas[codigo]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ErroSaida"
        )


def test_limites_do_pedido_e_dos_rascunhos_aparecem_no_openapi_para_o_front(openapi):
    # arrange
    esquema = openapi["components"]["schemas"]["GerarEntrada"]["properties"]

    # assert
    assert esquema["pedido"]["maxLength"] == 4000 and esquema["pedido"]["minLength"] == 1
    assert esquema["rascunhos"]["maxItems"] == 10
