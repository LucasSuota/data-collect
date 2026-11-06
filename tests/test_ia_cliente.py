import ast
import logging
import sys
import types
from pathlib import Path

import pytest

from forms.ia import cliente as modulo
from forms.ia.cliente import (
    ClienteAnthropic,
    ClienteFalso,
    IaIndisponivel,
    criar_cliente,
)

RAIZ = Path(__file__).resolve().parent.parent / "src" / "forms"


# --- cliente falso ---


def test_cliente_falso_responde_na_ordem_e_registra_o_que_recebeu():
    # arrange
    falso = ClienteFalso(["primeira", "segunda"])

    # act
    a = falso.completar("sistema A", "pergunta 1", maximo_de_tokens=100)
    b = falso.completar("sistema B", "pergunta 2", maximo_de_tokens=100)

    # assert
    assert (a, b) == ("primeira", "segunda")
    assert falso.chamadas == [("sistema A", "pergunta 1"), ("sistema B", "pergunta 2")]


def test_cliente_falso_sem_resposta_roteirizada_falha_alto():
    # arrange
    falso = ClienteFalso([])

    # act / assert: um teste que chama o LLM sem ter combinado a resposta é bug do teste
    with pytest.raises(AssertionError, match="sem resposta"):
        falso.completar("s", "m", maximo_de_tokens=10)


def test_cliente_falso_pode_simular_ia_indisponivel():
    # arrange
    falso = ClienteFalso([IaIndisponivel("sem internet")])

    # act / assert
    with pytest.raises(IaIndisponivel, match="sem internet"):
        falso.completar("s", "m", maximo_de_tokens=10)


def test_cliente_falso_vetoriza_de_forma_deterministica_ou_indisponivel():
    # arrange
    com = ClienteFalso([], vetores={"a": [1.0, 0.0], "b": [0.0, 1.0]})
    sem = ClienteFalso([])

    # act / assert
    assert com.vetorizar(["a", "b"]) == [[1.0, 0.0], [0.0, 1.0]]
    with pytest.raises(IaIndisponivel, match="embeddings"):
        sem.vetorizar(["a"])


# --- criar_cliente: sem chave, indisponível ---


def test_sem_chave_o_cliente_sinaliza_indisponibilidade_em_portugues():
    # act / assert
    with pytest.raises(IaIndisponivel) as excecao:
        criar_cliente({})

    assert "ANTHROPIC_API_KEY" in str(excecao.value)


@pytest.mark.parametrize("chave", ["", "   "])
def test_chave_vazia_tambem_e_indisponivel(chave):
    with pytest.raises(IaIndisponivel):
        criar_cliente({"ANTHROPIC_API_KEY": chave})


def test_com_chave_cria_o_cliente_real_sem_chamar_a_rede():
    # act
    cliente = criar_cliente({"ANTHROPIC_API_KEY": "sk-teste", "FORMS_LLM_MODELO": "modelo-x"})

    # assert
    assert isinstance(cliente, ClienteAnthropic)


def test_o_modelo_padrao_e_o_mais_recente_e_pode_ser_trocado_por_variavel():
    # act
    padrao = criar_cliente({"ANTHROPIC_API_KEY": "k"})
    trocado = criar_cliente({"ANTHROPIC_API_KEY": "k", "FORMS_LLM_MODELO": "outro"})

    # assert
    assert padrao.modelo == modulo.MODELO_PADRAO and trocado.modelo == "outro"


# --- cliente real, com um SDK falso no lugar do anthropic ---


class _SdkFalso:
    """Imita o mínimo do SDK `anthropic`: o teste nunca toca a rede nem exige a biblioteca."""

    class APIConnectionError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APIStatusError(Exception):
        pass

    def __init__(self, resposta="texto da IA", erro=None):
        self.resposta = resposta
        self.erro = erro
        self.chamadas = []
        sdk = self

        class Anthropic:
            def __init__(self, api_key, **opcoes):
                sdk.chave = api_key
                self.messages = self

            def create(self, **argumentos):
                sdk.chamadas.append(argumentos)
                if sdk.erro:
                    raise sdk.erro
                bloco = types.SimpleNamespace(type="text", text=sdk.resposta)
                return types.SimpleNamespace(content=[bloco])

        self.Anthropic = Anthropic


@pytest.fixture
def sdk(monkeypatch):
    falso = _SdkFalso()
    modulo_falso = types.ModuleType("anthropic")
    for nome in (
        "Anthropic",
        "APIConnectionError",
        "AuthenticationError",
        "RateLimitError",
        "APIStatusError",
    ):
        setattr(modulo_falso, nome, getattr(falso, nome))
    monkeypatch.setitem(sys.modules, "anthropic", modulo_falso)
    return falso


def test_cliente_real_envia_sistema_mensagem_e_limite_e_devolve_o_texto(sdk):
    # arrange
    cliente = ClienteAnthropic("sk-teste", "modelo-x")

    # act
    texto = cliente.completar("Seja breve.", "Olá", maximo_de_tokens=300)

    # assert
    assert texto == "texto da IA"
    (chamada,) = sdk.chamadas
    assert chamada["model"] == "modelo-x" and chamada["max_tokens"] == 300
    assert chamada["system"] == "Seja breve."
    assert chamada["messages"] == [{"role": "user", "content": "Olá"}]


def test_cliente_real_junta_so_os_blocos_de_texto(sdk, monkeypatch):
    # arrange
    class Anthropic:
        def __init__(self, api_key, **o):
            self.messages = self

        def create(self, **a):
            return types.SimpleNamespace(
                content=[
                    types.SimpleNamespace(type="text", text="a"),
                    types.SimpleNamespace(type="tool_use", text="ignorado"),
                    types.SimpleNamespace(type="text", text="b"),
                ]
            )

    sys.modules["anthropic"].Anthropic = Anthropic

    # act / assert
    assert ClienteAnthropic("k", "m").completar("s", "m", maximo_de_tokens=10) == "ab"


@pytest.mark.parametrize(
    "erro", ["APIConnectionError", "AuthenticationError", "RateLimitError", "APIStatusError"]
)
def test_falha_do_servico_vira_ia_indisponivel_em_portugues(sdk, erro):
    # arrange
    sdk.erro = getattr(sdk, erro)("detalhe técnico")
    cliente = ClienteAnthropic("sk-teste", "m")

    # act
    with pytest.raises(IaIndisponivel) as excecao:
        cliente.completar("s", "m", maximo_de_tokens=10)

    # assert: mensagem para a pessoa, sem a chave nem o detalhe técnico
    assert "sk-teste" not in str(excecao.value)
    assert excecao.value.__cause__ is not None


def test_sem_o_sdk_instalado_a_ia_fica_indisponivel_em_vez_de_quebrar(monkeypatch):
    # arrange: import falha como se o pacote opcional não estivesse instalado
    monkeypatch.setitem(sys.modules, "anthropic", None)

    # act / assert
    with pytest.raises(IaIndisponivel, match="não está instalada"):
        ClienteAnthropic("k", "m").completar("s", "m", maximo_de_tokens=10)


def test_a_chave_nunca_aparece_em_log_nem_no_repr(sdk, caplog):
    # arrange
    cliente = ClienteAnthropic("sk-segredo-123", "m")

    # act
    with caplog.at_level(logging.DEBUG):
        cliente.completar("s", "m", maximo_de_tokens=10)

    # assert
    assert "sk-segredo-123" not in caplog.text
    assert "sk-segredo-123" not in repr(cliente) and "sk-segredo-123" not in str(cliente)


def test_embeddings_nao_tem_provedor_configurado_por_padrao(sdk):
    # act / assert: o Anthropic não oferece embeddings; o RAG cai no BM25 (AGENTS.md §2.5)
    with pytest.raises(IaIndisponivel, match="embeddings"):
        ClienteAnthropic("k", "m").vetorizar(["texto"])


# --- isolamento (AGENTS.md §3.3 e §5.1) ---


def _importa(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes.update(alias.name.split(".")[0] for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module.split(".")[0])
    return nomes


def test_o_sdk_do_llm_so_e_importado_em_ia_cliente():
    # arrange
    donos = [a for a in RAIZ.rglob("*.py") if "anthropic" in _importa(a)]

    # assert
    assert donos == [] or donos == [RAIZ / "ia" / "cliente.py"]
    # o import é preguiçoso (dentro da função), então nem esse arquivo o faz no topo
    topo = ast.parse((RAIZ / "ia" / "cliente.py").read_text(encoding="utf-8")).body
    assert not any(isinstance(n, ast.Import) and n.names[0].name == "anthropic" for n in topo)


def test_o_nucleo_nunca_importa_ia_nem_rag():
    # arrange
    nucleo = [a for a in RAIZ.rglob("*.py") if a.relative_to(RAIZ).parts[0] not in {"ia", "rag"}]

    # act
    infratores = [
        a.name
        for a in nucleo
        for modulo_importado in _importados_completos(a)
        if modulo_importado.startswith(("forms.ia", "forms.rag"))
    ]

    # assert: a única exceção é a raiz de composição, que carrega a extensão se ela existir
    assert set(infratores) <= {"app.py"}


def _importados_completos(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    completos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module:
            completos.add(no.module)
        elif isinstance(no, ast.Import):
            completos.update(alias.name for alias in no.names)
    return completos
