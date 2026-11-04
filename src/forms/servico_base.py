"""Peças comuns aos casos de uso: transação e campos compartilhados dos formulários publicados.

Fica separado de `servico.py` para os módulos de casos de uso (formulários, registros, pastas)
usarem as mesmas regras sem importar uns aos outros.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from forms import repositorio, validacao
from forms.banco import Conexao
from forms.formulas import TipoFormula
from forms.models import Formulario, NaoEncontrado, ValorJson, Versao
from forms.validacao import CampoCompartilhado, Origens

# --- transação ---


@contextmanager
def transacao(conexao: Conexao) -> Iterator[None]:
    """Atomicidade de um caso de uso: ou tudo entra, ou nada. A conexão é `autocommit`, então
    `transaction()` abre um BEGIN real (ou um savepoint, se já houver uma transação)."""
    with conexao.transaction():
        yield


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
    conexao: Conexao,
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
    conexao: Conexao,
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


@dataclass
class Cache:
    """Evita refazer, na mesma operação, a análise das mesmas definições publicadas."""

    compartilhados: dict[int, dict[str, CampoCompartilhado]] = field(default_factory=dict)
    tipos_calculados: dict[int, dict[str, TipoFormula]] = field(default_factory=dict)


def tipos_calculados_da_versao(
    conexao: Conexao, versao: Versao, cache: Cache
) -> dict[str, TipoFormula]:
    """Tipo inferido de cada campo `calculado` de uma versão (não é guardado: sai da análise)."""
    if versao.id not in cache.tipos_calculados:
        origens = origens_publicadas(
            conexao,
            [(c.id, c.formulario) for c in versao.definicao.campos if c.formulario],
            cache.compartilhados,
        )
        analise = validacao.analisar_definicao(versao.definicao.para_json(), origens)
        cache.tipos_calculados[versao.id] = dict(analise.tipos_calculados)
    return cache.tipos_calculados[versao.id]
