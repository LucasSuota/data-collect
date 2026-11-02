"""Peças comuns aos casos de uso: transação e campos compartilhados dos formulários publicados.

Fica separado de `servico.py` para os módulos de casos de uso (formulários, registros, anexos)
usarem as mesmas regras sem importar uns aos outros.
"""

import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from forms import repositorio, validacao
from forms.models import Formulario, NaoEncontrado, ValorJson
from forms.validacao import CampoCompartilhado, Origens

# --- transação ---


@contextmanager
def transacao(conexao: sqlite3.Connection) -> Iterator[None]:
    """BEGIN explícito: sem ele o `sqlite3` não abre transação para DDL e, aqui, também deixaria
    uma falha no meio de um lote com formulários já gravados."""
    conexao.execute("BEGIN")
    try:
        yield
    except BaseException:
        conexao.rollback()
        raise
    conexao.commit()


# --- campos compartilhados de formulários já publicados ---


def referencias_brutas(definicao: ValorJson) -> list[tuple[str, str]]:
    """(id do campo, nome do formulário) de cada referência, tolerando JSON malformado."""
    campos = definicao.get("campos") if isinstance(definicao, dict) else None
    if not isinstance(campos, list):
        return []
    return [
        (campo["id"], campo["formulario"])
        for campo in campos
        if isinstance(campo, dict)
        and campo.get("tipo") == "referencia"
        and isinstance(campo.get("id"), str)
        and isinstance(campo.get("formulario"), str)
    ]


def origens_publicadas(
    conexao: sqlite3.Connection,
    referencias: Sequence[tuple[str, str]],
    cache: dict[int, dict[str, CampoCompartilhado]],
) -> Origens:
    origens: dict[str, Mapping[str, CampoCompartilhado]] = {}
    for _, nome in referencias:
        formulario = repositorio.obter_formulario_por_nome(conexao, nome)
        if formulario is not None:
            origens[nome] = compartilhados_publicados(conexao, formulario, cache)
    return origens


def compartilhados_publicados(
    conexao: sqlite3.Connection,
    formulario: Formulario,
    cache: dict[int, dict[str, CampoCompartilhado]],
) -> dict[str, CampoCompartilhado]:
    """Campos que a versão atual de um formulário publicado compartilha.

    O tipo de um `calculado` compartilhado não é guardado: sai de analisar de novo a definição
    publicada, o que exige as origens dela. O grafo é acíclico, então a recursão termina.
    """
    if formulario.id in cache:
        return cache[formulario.id]
    try:
        definicao = repositorio.obter_versao_atual(conexao, formulario.id).definicao
    except NaoEncontrado:  # formulário sem versão publicada não compartilha nada
        cache[formulario.id] = {}
        return {}
    origens = origens_publicadas(
        conexao,
        [(campo.id, campo.formulario) for campo in definicao.campos if campo.formulario],
        cache,
    )
    analise = validacao.analisar_definicao(definicao.para_json(), origens)
    compartilhados = validacao.compartilhados_da_definicao(definicao, analise.tipos_calculados)
    cache[formulario.id] = compartilhados
    return compartilhados
