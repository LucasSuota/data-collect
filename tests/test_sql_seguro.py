"""Guarda contra SQL injection (AGENTS.md §12): varredura do código-fonte.

O `ruff` (regra S608) já recusa SQL montado por string; este teste é a segunda barreira e a que
roda mesmo se alguém desligar a regra: nenhuma chamada a `execute` usa `%` ou `.format`, e SQL
dinâmico (f-string ou concatenação) só existe com `noqa: S608` e justificativa na mesma linha.
"""

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1] / "src" / "forms"
ARQUIVOS = sorted(p for p in RAIZ.rglob("*.py"))


def _chamadas_de_execute(arvore: ast.AST):
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr in {"execute", "executemany"}
            and no.args
        ):
            yield no


def _so_constantes(no: ast.AST) -> bool:
    """`CONSTANTE_DO_MODULO + "texto"`: junta só pedaços fixos, sem dado de fora."""
    if isinstance(no, ast.Constant):
        return isinstance(no.value, str)
    if isinstance(no, ast.Name):
        return no.id.isupper() or no.id.startswith("_SELECT")
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        return _so_constantes(no.left) and _so_constantes(no.right)
    return False


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_nenhum_execute_monta_sql_com_percent_ou_format(arquivo: Path):
    # arrange
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

    # act
    maus = []
    for chamada in _chamadas_de_execute(arvore):
        sql = chamada.args[0]
        for no in ast.walk(sql):
            formatado = isinstance(no, ast.BinOp) and isinstance(no.op, ast.Mod)
            com_format = (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "format"
            )
            if formatado or com_format:
                maus.append(chamada.lineno)

    # assert
    assert maus == []


@pytest.mark.parametrize("arquivo", ARQUIVOS, ids=lambda p: p.name)
def test_sql_dinamico_so_existe_com_noqa_e_justificativa_na_linha(arquivo: Path):
    # arrange
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    arvore = ast.parse("\n".join(linhas))

    # act: f-string ou concatenação como SQL
    sem_justificativa = []
    for chamada in _chamadas_de_execute(arvore):
        sql = chamada.args[0]
        dinamico = isinstance(sql, ast.JoinedStr) or isinstance(sql, ast.BinOp)
        if not dinamico or _so_constantes(sql):
            continue
        trecho = "\n".join(linhas[chamada.lineno - 1 : (sql.end_lineno or chamada.lineno) + 1])
        if "noqa: S608" not in trecho:
            sem_justificativa.append(chamada.lineno)

    # assert
    assert sem_justificativa == []


def test_o_ruff_tem_a_regra_s608_ligada():
    # arrange
    pyproject = (RAIZ.parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    # act / assert
    assert '"S608"' in pyproject


def test_filtro_por_json_so_aceita_campo_da_definicao_e_com_formato_de_identificador():
    # arrange
    from forms.models import ValorInvalido
    from forms.repositorio import FiltroDeIgualdade, _caminho_json

    # act / assert
    assert _caminho_json(FiltroDeIgualdade("obs", "x"), {"obs"}) == ["obs"]
    for malicioso in ["a') OR 1=1 --", 'x"; DROP TABLE registros; --', "$.dados"]:
        with pytest.raises(ValorInvalido):  # na lista permitida, mas sem formato de identificador
            _caminho_json(FiltroDeIgualdade(malicioso, "x"), {"obs", malicioso})
    with pytest.raises(ValorInvalido):  # identificador válido, mas fora da definição
        _caminho_json(FiltroDeIgualdade("fantasma", "x"), {"obs"})
