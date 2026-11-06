"""Extensões opcionais da API: rotas de módulos que podem não existir (AGENTS.md §3.1 e §5.1).

O núcleo nunca importa `ia/` nem `rag/`. Em vez disso, cada módulo opcional publica um objeto
`EXTENSAO` num módulo `extensao`, e a montagem do app o procura **pelo nome**: se a pasta foi
removida, o app sobe normalmente, só sem essas rotas.
"""

import importlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from forms.api.esquemas import ErroDeCampoSaida, ErroSaida

MODULOS_OPCIONAIS = ("forms.ia.extensao", "forms.rag.extensao")

type Tratador = Callable[[Request, Exception], Awaitable[Response]]


@dataclass(frozen=True)
class Extensao:
    nome: str
    roteador: APIRouter
    # Exceção de domínio do módulo -> resposta. O mais específico vence o `ErroDeDominio` geral.
    tratadores: Mapping[type[Exception], Tratador] = field(default_factory=dict)


def descobrir_extensoes(modulos: Sequence[str] = MODULOS_OPCIONAIS) -> tuple[Extensao, ...]:
    encontradas = []
    for nome in modulos:
        try:
            modulo = importlib.import_module(nome)
        except ModuleNotFoundError as erro:
            # Só a ausência do próprio módulo (ou de um pacote pai) é aceita: um `import` quebrado
            # lá dentro é bug de verdade e precisa aparecer, não sumir com as rotas.
            if erro.name is not None and (nome == erro.name or nome.startswith(f"{erro.name}.")):
                continue
            raise
        encontradas.append(modulo.EXTENSAO)
    return tuple(encontradas)


def resposta_de_erro(
    status: int,
    detalhe: str,
    erros: list[ErroDeCampoSaida] | None = None,
    codigo: str | None = None,
) -> JSONResponse:
    """O formato uniforme de erro (§5.3), usado pelo app e pelas extensões."""
    corpo = ErroSaida(detalhe=detalhe, erros=erros or [], codigo=codigo)
    conteudo = corpo.model_dump(mode="json")
    if conteudo["codigo"] is None:
        del conteudo["codigo"]  # só aparece quando o front precisa agir (`token_expirado`...)
    return JSONResponse(status_code=status, content=conteudo)
