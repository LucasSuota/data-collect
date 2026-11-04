"""Rascunho de versão: a próxima versão em edição, compartilhada pela equipe (AGENTS.md §2.2).

Salvar aceita definição incompleta (como `validar`); só publicar valida de verdade. Versões
publicadas continuam imutáveis: o rascunho é uma linha à parte, com `revisao` para a concorrência.
"""

from datetime import datetime

from forms import repositorio
from forms.banco import Conexao
from forms.models import ConflitoDeRevisao, NaoEncontrado, ValorInvalido, ValorJson
from forms.repositorio import RascunhoGuardado
from forms.servico_base import transacao

TAMANHO_MAXIMO_EM_CAMPOS = 500  # um rascunho absurdo não vira um problema de memória


def obter_rascunho(conexao: Conexao, formulario_id: int) -> RascunhoGuardado:
    repositorio.obter_formulario(conexao, formulario_id)
    rascunho = repositorio.obter_rascunho(conexao, formulario_id)
    if rascunho is None:
        raise NaoEncontrado(f"O formulário {formulario_id} não tem rascunho.")
    return rascunho


def salvar_rascunho(
    conexao: Conexao,
    formulario_id: int,
    definicao: ValorJson,
    revisao: int | None,
    agora: datetime,
) -> RascunhoGuardado:
    """Cria o rascunho (sem `revisao`) ou o substitui (com a `revisao` lida)."""
    if not isinstance(definicao, dict):
        raise ValorInvalido("O rascunho deve ser um objeto JSON com a lista 'campos'.")
    campos = definicao.get("campos")
    if isinstance(campos, list) and len(campos) > TAMANHO_MAXIMO_EM_CAMPOS:
        raise ValorInvalido(f"O rascunho tem campos demais (máximo {TAMANHO_MAXIMO_EM_CAMPOS}).")
    repositorio.obter_formulario(conexao, formulario_id)
    with transacao(conexao):
        # Trava o formulário: duas primeiras gravações simultâneas não criam dois rascunhos.
        conexao.execute(
            "SELECT 1 FROM formularios WHERE id = %s AND grupo_id = %s FOR UPDATE",
            (formulario_id, conexao.grupo_id),
        )
        atual = repositorio.obter_rascunho(conexao, formulario_id)
        if atual is None:
            if revisao is not None:
                raise NaoEncontrado("Este rascunho foi descartado ou publicado. Recarregue.")
            base = repositorio.obter_versao_atual(conexao, formulario_id).id
            repositorio.criar_rascunho(conexao, formulario_id, definicao, base, agora)
        elif revisao is None or not repositorio.atualizar_rascunho(
            conexao, formulario_id, definicao, revisao, agora
        ):
            raise ConflitoDeRevisao(
                "Outra pessoa alterou este rascunho. Recarregue antes de salvar."
            )
    return obter_rascunho(conexao, formulario_id)


def descartar_rascunho(conexao: Conexao, formulario_id: int) -> None:
    repositorio.obter_formulario(conexao, formulario_id)
    with transacao(conexao):
        if not repositorio.apagar_rascunho(conexao, formulario_id):
            raise NaoEncontrado(f"O formulário {formulario_id} não tem rascunho.")
