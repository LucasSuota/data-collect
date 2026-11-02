import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from forms import cli, servico
from forms.repositorio import abrir_conexao

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
TEMPLATES = Path(__file__).parent.parent / "templates"
CORPO = str(TEMPLATES / "corpo_de_prova.json")


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    return tmp_path / "forms.db"


def _rodar(banco: Path, *argumentos: str) -> int:
    return cli.main(["--banco", str(banco), *argumentos], relogio=lambda: AGORA)


def _dados(tmp_path: Path, **valores: object) -> str:
    arquivo = tmp_path / "dados.json"
    arquivo.write_text(json.dumps(valores), encoding="utf-8")
    return str(arquivo)


DADOS_VALIDOS = {"fck_mpa": 25, "diametro_mm": 100, "data_moldagem": "2026-11-01", "carga_kn": 200}


# --- importar template ---


def test_importar_template_cria_o_formulario_e_conta_na_saida(banco, capsys):
    # act
    codigo = _rodar(banco, "importar-template", CORPO)

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0 and "corpo_de_prova" in saida and "versão 1" in saida
    conexao = abrir_conexao(banco)
    assert [f.nome for f in servico.listar_formularios(conexao)] == ["corpo_de_prova"]


def test_importar_varios_templates_de_uma_vez(banco, capsys):
    # act
    codigo = _rodar(banco, "importar-template", CORPO, str(TEMPLATES / "inspecao_obra.json"))

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0 and "corpo_de_prova" in saida and "inspecao_obra" in saida


def test_importar_template_com_nome_explicito(banco, capsys):
    # act
    codigo = _rodar(banco, "importar-template", CORPO, "--nome", "Corpo 2")

    # assert
    assert codigo == 0 and "Corpo 2" in capsys.readouterr().out


def test_importar_template_invalido_falha_com_mensagem_em_portugues_e_codigo_diferente_de_zero(
    banco, tmp_path, capsys
):
    # arrange
    ruim = tmp_path / "ruim.json"
    ruim.write_text(json.dumps({"campos": [{"id": "a", "tipo": "telefone", "rotulo": "A"}]}))

    # act
    codigo = _rodar(banco, "importar-template", str(ruim))

    # assert
    erro = capsys.readouterr().err
    assert codigo == 1 and "a.tipo" in erro and "telefone" in erro
    assert servico.listar_formularios(abrir_conexao(banco)) == []


def test_importar_template_inexistente_falha_com_erro_claro(banco, tmp_path, capsys):
    # act
    codigo = _rodar(banco, "importar-template", str(tmp_path / "nada.json"))

    # assert
    assert codigo == 1 and "nada.json" in capsys.readouterr().err


def test_importar_o_mesmo_template_duas_vezes_falha_por_nome_repetido(banco, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    codigo = _rodar(banco, "importar-template", CORPO)

    # assert
    assert codigo == 1 and "Já existe" in capsys.readouterr().err


# --- criar registro ---


def test_criar_registro_a_partir_de_json_mostra_o_id_e_os_calculados(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    codigo = _rodar(
        banco, "criar-registro", "corpo_de_prova", "--dados", _dados(tmp_path, **DADOS_VALIDOS)
    )

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0 and "Registro 1 criado" in saida
    assert "2026-11-29" in saida and "25,5" in saida


def test_formulario_pode_ser_dado_pelo_id_em_vez_do_nome(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    codigo = _rodar(banco, "criar-registro", "1", "--dados", _dados(tmp_path, **DADOS_VALIDOS))

    # assert
    assert codigo == 0 and "Registro 1 criado" in capsys.readouterr().out


def test_dados_podem_vir_da_entrada_padrao(banco, monkeypatch, capsys):
    # arrange
    import io

    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(DADOS_VALIDOS)))

    # act
    codigo = _rodar(banco, "criar-registro", "corpo_de_prova", "--dados", "-")

    # assert
    assert codigo == 0


def test_registro_invalido_lista_todos_os_erros_por_campo_e_nao_grava(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    codigo = _rodar(
        banco, "criar-registro", "corpo_de_prova", "--dados", _dados(tmp_path, diametro_mm="abc")
    )

    # assert
    erro = capsys.readouterr().err
    assert codigo == 1
    assert "fck_mpa" in erro and "diametro_mm" in erro and "data_moldagem" in erro
    _rodar(banco, "listar", "corpo_de_prova")
    assert "0 registro" in capsys.readouterr().out


def test_dados_que_nao_sao_json_geram_erro_claro(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text("{nao e json")

    # act
    codigo = _rodar(banco, "criar-registro", "corpo_de_prova", "--dados", str(arquivo))

    # assert
    assert codigo == 1 and "JSON" in capsys.readouterr().err


def test_formulario_inexistente_falha_com_mensagem(banco, tmp_path, capsys):
    # act
    codigo = _rodar(banco, "criar-registro", "fantasma", "--dados", _dados(tmp_path))

    # assert
    assert codigo == 1 and "fantasma" in capsys.readouterr().err


def test_versao_explicita_antiga_e_respeitada(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    conexao = abrir_conexao(banco)
    servico.publicar_versao(
        conexao, 1, {"campos": [{"id": "x", "tipo": "texto", "rotulo": "X"}]}, AGORA
    )
    capsys.readouterr()

    # act
    codigo = _rodar(
        banco,
        "criar-registro",
        "corpo_de_prova",
        "--versao",
        "1",
        "--dados",
        _dados(tmp_path, **DADOS_VALIDOS),
    )

    # assert
    assert codigo == 0


# --- listar ---


def test_listar_sem_formulario_mostra_os_formularios(banco, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO, str(TEMPLATES / "inspecao_obra.json"))
    capsys.readouterr()

    # act
    codigo = _rodar(banco, "listar")

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0 and "corpo_de_prova" in saida and "inspecao_obra" in saida


def test_listar_registros_mostra_colunas_e_valores_formatados(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    _rodar(banco, "criar-registro", "corpo_de_prova", "--dados", _dados(tmp_path, **DADOS_VALIDOS))
    capsys.readouterr()

    # act
    codigo = _rodar(banco, "listar", "corpo_de_prova")

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0
    assert "fck especificado (MPa)" in saida and "Resistência (MPa)" in saida
    assert "25,5" in saida and "Sim" in saida and "1 registro" in saida


def test_listar_com_filtro_e_paginacao(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", str(TEMPLATES / "inspecao_obra.json"))
    for situacao in ("Conforme", "Pendente", "Conforme"):
        dados = {"responsavel": "Ana", "data_inspecao": "2026-11-02", "situacao": situacao}
        _rodar(banco, "criar-registro", "inspecao_obra", "--dados", _dados(tmp_path, **dados))
    capsys.readouterr()

    # act
    codigo = _rodar(
        banco, "listar", "inspecao_obra", "--filtro", "situacao=Conforme", "--limite", "1"
    )

    # assert
    saida = capsys.readouterr().out
    assert codigo == 0 and "2 registro" in saida and saida.count("Conforme") == 1


def test_filtro_mal_formado_ou_em_campo_nao_filtravel_falha(banco, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    sem_igual = _rodar(banco, "listar", "corpo_de_prova", "--filtro", "fck_mpa")
    campo_numerico = _rodar(banco, "listar", "corpo_de_prova", "--filtro", "fck_mpa=25")

    # assert
    assert sem_igual == 1 and campo_numerico == 1
    assert "fck_mpa" in capsys.readouterr().err


# --- exportar ---


def test_exportar_grava_o_csv_para_o_excel_em_portugues(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    _rodar(banco, "criar-registro", "corpo_de_prova", "--dados", _dados(tmp_path, **DADOS_VALIDOS))
    capsys.readouterr()
    destino = tmp_path / "saida.csv"

    # act
    codigo = _rodar(banco, "exportar", "corpo_de_prova", "--saida", str(destino))

    # assert
    assert codigo == 0 and str(destino) in capsys.readouterr().out
    conteudo = destino.read_bytes()
    assert conteudo.startswith(b"\xef\xbb\xbf")
    linhas = conteudo.decode("utf-8-sig").split("\r\n")
    assert linhas[0].startswith("fck especificado (MPa);Diâmetro (mm);")
    assert ";25,5;" in linhas[1]


def test_exportar_com_filtro_usa_a_mesma_regra_da_listagem(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    _rodar(banco, "criar-registro", "corpo_de_prova", "--dados", _dados(tmp_path, **DADOS_VALIDOS))
    capsys.readouterr()

    # act
    codigo = _rodar(
        banco,
        "exportar",
        "corpo_de_prova",
        "--saida",
        str(tmp_path / "x.csv"),
        "--filtro",
        "conforme=false",
    )

    # assert
    assert codigo == 0
    texto = (tmp_path / "x.csv").read_bytes().decode("utf-8-sig")
    assert texto.count("\r\n") == 1  # só o cabeçalho, sem registros


def test_exportar_sem_saida_escreve_na_saida_padrao(banco, tmp_path, capsys):
    # arrange
    _rodar(banco, "importar-template", CORPO)
    capsys.readouterr()

    # act
    codigo = _rodar(banco, "exportar", "corpo_de_prova")

    # assert
    assert codigo == 0
    assert capsys.readouterr().out.startswith("\ufefffck especificado (MPa);")  # com BOM


# --- uso e estrutura ---


def test_sem_comando_ou_comando_desconhecido_e_erro_de_uso(banco, capsys):
    # act / assert: o argparse sai com código 2
    with pytest.raises(SystemExit) as sem_comando:
        cli.main(["--banco", str(banco)])
    with pytest.raises(SystemExit) as desconhecido:
        cli.main(["--banco", str(banco), "voar"])
    assert sem_comando.value.code == 2 and desconhecido.value.code == 2


def test_ajuda_esta_em_portugues(capsys):
    # act
    with pytest.raises(SystemExit) as saida:
        cli.main(["--help"])

    # assert
    texto = capsys.readouterr().out
    assert saida.value.code == 0
    assert "importar-template" in texto and "criar-registro" in texto and "exportar" in texto


def test_cli_nao_importa_repositorio_nem_regras_do_nucleo():
    # arrange: a CLI é fina, só chama o `servico` (AGENTS.md §3.3 e §5.1)
    import ast

    arvore = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    importados = {(no.module or "") for no in ast.walk(arvore) if isinstance(no, ast.ImportFrom)}

    # assert
    proibidos = {
        "forms.repositorio",
        "forms.validacao",
        "forms.formulas",
        "forms.tipos_campo",
        "sqlite3",
    }
    assert importados.isdisjoint(proibidos)
    nomes = {
        alias.name for no in ast.walk(arvore) if isinstance(no, ast.Import) for alias in no.names
    }
    assert "sqlite3" not in nomes
