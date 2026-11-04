"""O contrato com o `frontend/` (AGENTS.md §5.3): renomear ou remover campo de resposta, ou
mudar o conjunto de rotas, faz um destes testes falhar. Mudança incompatível exige sinalizar."""

import json
from pathlib import Path

import pytest

from forms.api import Configuracao, criar_app, descobrir_extensoes
from forms.exportar_openapi import gerar
from forms.exportar_openapi import main as exportar

# Campos de cada modelo de resposta: nome -> obrigatório. É o JSON esperado pelo front.
MODELOS_DE_RESPOSTA = {
    "AceitarConviteSaida": {"equipe": True},
    "BuscaFormularioSaida": {"id": True, "nome": True},
    "BuscaRegistroSaida": {"id": True, "formulario_id": True, "formulario": True},
    "BuscaSaida": {"formularios": True, "registros": True},
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
        "ia": False,
    },
    "CargoResumoSaida": {"id": True, "nome": True},
    "CargoSaida": {
        "id": True,
        "nome": True,
        "descricao": True,
        "padrao": True,
        "permissoes": True,
        "pessoas": True,
    },
    "CatalogoDePermissoesSaida": {"permissoes": True},
    "CatalogoSaida": {"tipos": True, "funcoes": True, "constantes": True, "nomes_reservados": True},
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
    "ConsentimentoSaida": {"documento": True, "versao": True, "aceito_em": True},
    "ConsentimentosSaida": {"aceites": True, "pendentes": True},
    "ConstanteDoCatalogoSaida": {"nome": True, "valor": True, "tipo": True, "descricao": True},
    "ContagensSaida": {
        "campo_status": True,
        "total": True,
        "conforme": True,
        "nao_conforme": True,
        "erro": True,
        "aguardando": True,
    },
    "ConviteCriadoSaida": {"convite": True, "token": True},
    "ConviteSaida": {
        "id": True,
        "email": True,
        "cargo": True,
        "criado_em": True,
        "expira_em": True,
    },
    "DefinicaoSaida": {"campos": True, "exibicao": False},
    "DestaqueSaida": {"rotulo": True, "valor": True, "unidade": True},
    "DocumentoLegalSaida": {"id": True, "titulo": True, "versao": True, "markdown": True},
    "DocumentosLegaisSaida": {"documentos": True},
    "EquipeDaPessoaSaida": {
        "id": True,
        "nome": True,
        "ativa": True,
        "cargo": True,
        "permissoes": True,
    },
    "EquipeSaida": {"id": True, "nome": True},
    "ErroDeCampoSaida": {"campo": True, "mensagem": True, "posicao": False},
    "ErroSaida": {"detalhe": True, "erros": False, "codigo": False},
    "EuSaida": {"pessoa": True, "equipes": True, "termos_pendentes": True},
    "ExemploSaida": {"nome": True, "descricao": True, "campos": True, "depende_de": True},
    "ExemplosImportadosSaida": {"formularios": True},
    "ExibicaoSaida": {"destaque": False, "status": False, "resumo": False},
    "FormularioDetalheSaida": {
        "id": True,
        "nome": True,
        "criado_em": True,
        "versao_atual": True,
        "pasta_id": False,
    },
    "FuncaoDoCatalogoSaida": {"nome": True, "assinatura": True, "descricao": True, "exemplo": True},
    "GerarSaida": {"formularios": True},
    "HistoricoSaida": {
        "id": True,
        "usuario_id": True,
        "pessoa": True,
        "quando": True,
        "acao": True,
        "valores_anteriores": True,
        "motivo": True,
    },
    "ListagemDeRegistrosSaida": {
        "versao_id": True,
        "colunas": True,
        "itens": True,
        "total": True,
        "exibicao": True,
    },
    "MembroSaida": {
        "usuario_id": True,
        "nome": True,
        "email": True,
        "cargo": True,
        "ativo": True,
        "entrou_em": True,
    },
    "NotificacaoSaida": {
        "id": True,
        "tipo": True,
        "referencia": True,
        "lida": True,
        "criada_em": True,
    },
    "NotificacoesSaida": {"itens": True, "nao_lidas": True},
    "PastaSaida": {"id": True, "nome": True, "pasta_pai_id": True, "criado_em": True},
    "PermissaoSaida": {"id": True, "grupo": True, "rotulo": True, "descricao": True},
    "PessoaResumoSaida": {"id": True, "nome": True},
    "PessoaSaida": {"id": True, "nome": True, "email": True},
    "PosicaoSaida": {"inicio": True, "fim": True},
    "PreviaSaida": {"valida": True, "erros": True, "calculados": True},
    "ProgressoSaida": {"tour_concluido": True, "passo": True, "checklist_dispensado": True},
    "ProntoSaida": {"status": True, "migracao": True},
    "RascunhoGeradoSaida": {"nome": True, "definicao": True, "erros": True},
    "RascunhoSaida": {
        "formulario_id": True,
        "definicao": True,
        "base_versao_id": True,
        "revisao": True,
        "atualizado_por": True,
        "atualizado_em": True,
    },
    "RegistroRecenteSaida": {
        "id": True,
        "formulario_id": True,
        "formulario": True,
        "atualizado_em": True,
        "estado": True,
        "destaque": True,
    },
    "RegistroSaida": {
        "id": True,
        "formulario_id": True,
        "versao_id": True,
        "dados": True,
        "revisao": True,
        "criado_por": True,
        "atualizado_por": True,
        "criado_em": True,
        "atualizado_em": True,
        "estado": False,
    },
    "RespostaSaida": {"encontrou": True, "texto": True, "usou_ia": True, "trechos": True},
    "ResultadoCalculadoSaida": {"valor": True, "erro": True},
    "ResumoDeFormularioSaida": {
        "id": True,
        "nome": True,
        "criado_em": True,
        "versao_atual_id": True,
        "versao_atual_numero": True,
        "pasta_id": False,
    },
    "ResumoDeVersaoSaida": {"id": True, "numero": True, "publicada_em": True},
    "ResumoSaida": {"titulo": True, "paragrafos": True, "destaques": True, "total": True},
    "SaudeSaida": {"status": True},
    "TipoDoCatalogoSaida": {"id": True, "rotulo": True, "propriedades": True},
    "TrechoSaida": {"arquivo": True, "titulo": True, "texto": True, "pontuacao": True},
    "ValidarSaida": {"valida": True, "erros": True},
    "VersaoSaida": {
        "id": True,
        "formulario_id": True,
        "numero": True,
        "definicao": True,
        "publicada_em": True,
    },
}

MODELOS_DE_ENTRADA = {
    "CargoEntrada": {"nome": True, "descricao": False, "permissoes": True},
    "ConsentimentoEntrada": {"documentos": False},
    "ConviteEntrada": {"email": True, "cargo_id": True},
    "DuplicarEntrada": {"nome": False},
    "EquipeEntrada": {"nome": True},
    "FormularioEntrada": {"nome": True, "definicao": True, "pasta_id": False},
    "GerarEntrada": {"pedido": True, "rascunhos": False},
    "ImportarExemplosEntrada": {"nomes": True},
    "LoteEntrada": {"formularios": True},
    "MoverFormularioEntrada": {"pasta_id": True},
    "PastaAtualizacao": {"nome": True, "pasta_pai_id": True},
    "PastaEntrada": {"nome": True, "pasta_pai_id": False},
    "PerguntaEntrada": {"pergunta": True},
    "PreviaEntrada": {"definicao": True, "valores": False},
    "ProgressoEntrada": {"tour_concluido": True, "passo": True, "checklist_dispensado": True},
    "RascunhoEntrada": {"definicao": True, "revisao": False},
    "RegistroAtualizacao": {"dados": True, "revisao": True},
    "RegistroEntrada": {"versao_id": True, "dados": True},
    "TrocarCargoEntrada": {"cargo_id": True},
    "ValidarEntrada": {"definicao": True},
    "VersaoEntrada": {"definicao": True},
}

ROTAS = [
    ("delete", "/cargos/{cargo_id}"),
    ("delete", "/convites/{convite_id}"),
    ("delete", "/eu"),
    ("delete", "/formularios/{formulario_id}"),
    ("delete", "/formularios/{formulario_id}/rascunho"),
    ("delete", "/pastas/{pasta_id}"),
    ("delete", "/registros/{registro_id}"),
    ("get", "/busca"),
    ("get", "/cargos"),
    ("get", "/catalogo"),
    ("get", "/catalogo/permissoes"),
    ("get", "/consentimentos"),
    ("get", "/convites"),
    ("get", "/equipe"),
    ("get", "/eu"),
    ("get", "/eu/exportar"),
    ("get", "/eu/onboarding"),
    ("get", "/formularios"),
    ("get", "/formularios/{formulario_id}"),
    ("get", "/formularios/{formulario_id}/rascunho"),
    ("get", "/formularios/{formulario_id}/registros"),
    ("get", "/formularios/{formulario_id}/registros/contagens"),
    ("get", "/formularios/{formulario_id}/registros/exportar"),
    ("get", "/formularios/{formulario_id}/versoes"),
    ("get", "/formularios/{formulario_id}/versoes/{versao_id}"),
    ("get", "/healthz"),
    ("get", "/legal"),
    ("get", "/legal/{documento}"),
    ("get", "/membros"),
    ("get", "/notificacoes"),
    ("get", "/pastas"),
    ("get", "/readyz"),
    ("get", "/registros/recentes"),
    ("get", "/registros/{registro_id}"),
    ("get", "/registros/{registro_id}/historico"),
    ("get", "/templates"),
    ("post", "/assistente/perguntar"),
    ("post", "/cargos"),
    ("post", "/consentimentos"),
    ("post", "/convites"),
    ("post", "/convites/{token}/aceitar"),
    ("post", "/definicoes/gerar"),
    ("post", "/definicoes/previa"),
    ("post", "/definicoes/validar"),
    ("post", "/equipe/sair"),
    ("post", "/formularios"),
    ("post", "/formularios/lote"),
    ("post", "/formularios/{formulario_id}/duplicar"),
    ("post", "/formularios/{formulario_id}/rascunho/publicar"),
    ("post", "/formularios/{formulario_id}/registros"),
    ("post", "/formularios/{formulario_id}/resumo"),
    ("post", "/formularios/{formulario_id}/versoes"),
    ("post", "/membros/{usuario_id}/desativar"),
    ("post", "/membros/{usuario_id}/reativar"),
    ("post", "/notificacoes/{notificacao_id}/lida"),
    ("post", "/pastas"),
    ("post", "/templates/importar"),
    ("put", "/cargos/{cargo_id}"),
    ("put", "/equipe"),
    ("put", "/eu/onboarding"),
    ("put", "/formularios/{formulario_id}/pasta"),
    ("put", "/formularios/{formulario_id}/rascunho"),
    ("put", "/membros/{usuario_id}/cargo"),
    ("put", "/pastas/{pasta_id}"),
    ("put", "/registros/{registro_id}"),
]

# Respostas que não são JSON de modelo: 204 sem corpo, CSV e download.
SEM_MODELO = {
    ("delete", "/cargos/{cargo_id}"),
    ("delete", "/convites/{convite_id}"),
    ("delete", "/eu"),
    ("delete", "/formularios/{formulario_id}"),
    ("delete", "/formularios/{formulario_id}/rascunho"),
    ("delete", "/pastas/{pasta_id}"),
    ("delete", "/registros/{registro_id}"),
    ("get", "/eu/exportar"),
    ("get", "/formularios/{formulario_id}/registros/exportar"),
    ("post", "/equipe/sair"),
    ("post", "/membros/{usuario_id}/desativar"),
    ("post", "/membros/{usuario_id}/reativar"),
    ("post", "/notificacoes/{notificacao_id}/lida"),
    ("put", "/membros/{usuario_id}/cargo"),
}


@pytest.fixture(scope="module")
def openapi() -> dict:
    return criar_app(
        Configuracao(dsn="x", origens_cors=("http://localhost:5173",)),
        extensoes=descobrir_extensoes(),
    ).openapi()


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
    pydantic = {"HTTPValidationError", "ValidationError"}

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


# Rotas sem login: só têm os erros que podem dar (ex.: 404 em /legal/{documento}).
PUBLICAS_SEM_AUTENTICACAO = {
    ("get", "/healthz"),
    ("get", "/readyz"),
    ("get", "/legal"),
    ("get", "/legal/{documento}"),
    ("get", "/catalogo/permissoes"),
}


@pytest.mark.parametrize(
    ("metodo", "caminho"), [r for r in ROTAS if r not in PUBLICAS_SEM_AUTENTICACAO]
)
def test_todo_endpoint_autenticado_documenta_o_erro_uniforme_para_401_404_e_422(
    openapi, metodo, caminho
):
    # arrange
    respostas = openapi["paths"][caminho][metodo]["responses"]

    # assert
    for codigo in ("401", "404", "422"):
        esquema = respostas[codigo]["content"]["application/json"]["schema"]
        assert esquema["$ref"].endswith("/ErroSaida"), (codigo, caminho)


@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [
        ("delete", "/formularios/{formulario_id}"),
        ("delete", "/pastas/{pasta_id}"),
        ("delete", "/registros/{registro_id}"),
    ],
)
def test_exclusoes_documentam_o_409(openapi, metodo, caminho):
    # act / assert
    assert openapi["paths"][caminho][metodo]["responses"]["409"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/ErroSaida")


def test_a_autenticacao_bearer_esta_no_openapi_e_o_token_por_execucao_sumiu(openapi):
    # assert
    esquemas = openapi["components"]["securitySchemes"]
    assert esquemas["Bearer"]["type"] == "http" and esquemas["Bearer"]["scheme"] == "bearer"
    assert "TokenDaExecucao" not in esquemas


def test_rotas_publicas_nao_pedem_autenticacao_e_as_demais_pedem(openapi):
    # act
    publicas = {
        (metodo, caminho)
        for caminho, ops in openapi["paths"].items()
        for metodo, op in ops.items()
        if not op.get("security")
    }

    # assert
    assert publicas == PUBLICAS_SEM_AUTENTICACAO


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
        "meus",
        "filtro",
        "X-Equipe",
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
    assert json.loads(destino.read_text(encoding="utf-8")) == json.loads(gerar())
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
        arquivo.read_text(encoding="utf-8").replace('"0.2.0"', '"9.9.9"'), encoding="utf-8"
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
