"""Central de ajuda: guias em Markdown, lidos de `ajuda/` (AGENTS.md §2.16)."""

import pytest
from fastapi.testclient import TestClient

from forms.dominio.models import NaoEncontrado
from forms.infra import ajuda


def test_todos_os_guias_do_repositorio_tem_titulo_e_conteudo():
    # act
    guias = ajuda.listar()

    # assert
    assert {g.id for g in guias} >= set(ajuda.ORDEM)
    assert all(g.titulo and g.markdown.startswith("# ") for g in guias)


def test_guias_saem_na_ordem_de_leitura_e_os_novos_vao_depois(tmp_path):
    # arrange
    (tmp_path / "zzz-novo.md").write_text("# Novo\n\ntexto", encoding="utf-8")
    (tmp_path / "formulas.md").write_text("# Fórmulas\n\ntexto", encoding="utf-8")
    (tmp_path / "primeiros-passos.md").write_text("# Começo\n\ntexto", encoding="utf-8")

    # act
    ids = [g.id for g in ajuda.listar(tmp_path)]

    # assert
    assert ids == ["primeiros-passos", "formulas", "zzz-novo"]


def test_pasta_inexistente_nao_quebra_e_devolve_lista_vazia(tmp_path):
    # act / assert
    assert ajuda.listar(tmp_path / "nao-existe") == []


@pytest.mark.parametrize(
    "nome", ["../AGENTS", "../../etc/passwd", "a/b", "Formulas", "", "x.md", "%2e%2e"]
)
def test_nome_de_guia_com_cara_de_caminho_e_recusado_sem_tocar_no_disco(nome):
    # act / assert: path traversal (§12)
    with pytest.raises(NaoEncontrado):
        ajuda.ler(nome)


def test_guia_sem_titulo_usa_o_nome_do_arquivo(tmp_path):
    # arrange
    (tmp_path / "sem-titulo.md").write_text("só texto", encoding="utf-8")

    # act / assert
    assert ajuda.ler("sem-titulo", tmp_path).titulo == "sem-titulo"


def test_api_de_ajuda_e_publica_e_devolve_markdown(app):
    # act
    cliente = TestClient(app)
    lista = cliente.get("/ajuda")
    guia = cliente.get("/ajuda/formulas")

    # assert
    assert lista.status_code == 200 and len(lista.json()["guias"]) >= 10
    assert guia.json()["titulo"] == "Escrever fórmulas" and "```" in guia.json()["markdown"]


def test_api_guia_inexistente_ou_traversal_e_404(app):
    # act
    cliente = TestClient(app)

    # assert
    assert cliente.get("/ajuda/fantasma").status_code == 404
    assert cliente.get("/ajuda/..%2F..%2Fetc%2Fpasswd").status_code == 404


def test_cada_funcao_de_formula_do_catalogo_esta_no_guia_de_formulas(cliente):
    # arrange
    funcoes = [f["nome"] for f in cliente.get("/catalogo").json()["funcoes"]]
    guia = ajuda.ler("formulas").markdown

    # act / assert: o guia não pode ficar para trás do avaliador
    assert [f for f in funcoes if f"{f}(" not in guia] == []
