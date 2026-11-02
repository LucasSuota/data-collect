"""Rotas de IA da API: gerador de formulários e resumo de registros (AGENTS.md §2.5).

É uma extensão opcional: o núcleo a encontra pelo nome (`api_extensoes.py`) e o app funciona sem
esta pasta. Aqui só há HTTP; a regra está em `gerador.py`, `resumo.py` e `validacao.py`.
Nenhuma rota grava nada: o gerador devolve rascunhos e o resumo só lê.
"""

import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import Field

from forms import servico
from forms.api_esquemas import ErroDeCampoSaida, ErroSaida, FormularioEntrada, Modelo
from forms.api_extensoes import Extensao, resposta_de_erro
from forms.api_rotas import ERROS_COMUNS, DepConexao, esquema_do_token, ler_filtros
from forms.ia import gerador, resumo
from forms.ia.cliente import ClienteDeLLM, IaIndisponivel, criar_cliente
from forms.ia.gerador import MAXIMO_DE_FORMULARIOS, PEDIDO_MAXIMO, RespostaDaIaInvalida
from forms.ia.validacao import ResumoRejeitado

_ERROS_DA_IA = {
    502: {"model": ErroSaida, "description": "A IA respondeu, mas fora do formato esperado."},
    503: {"model": ErroSaida, "description": "IA indisponível (sem chave ou sem internet)."},
}


# --- modelos ---


class GerarEntrada(Modelo):
    pedido: str = Field(
        min_length=1,
        max_length=PEDIDO_MAXIMO,
        description="O que a pessoa quer, em texto livre.",
    )
    rascunhos: list[FormularioEntrada] = Field(
        default_factory=list,
        max_length=MAXIMO_DE_FORMULARIOS,
        description="Rascunhos em edição, para refinar (ex.: 'adicione o campo X').",
    )


class RascunhoGeradoSaida(Modelo):
    nome: str
    definicao: object = Field(description="Definição proposta; pode estar inválida (veja `erros`).")
    erros: list[ErroDeCampoSaida] = Field(
        description="Vazio quando passou na validação; senão, para a pessoa corrigir no construtor."
    )


class GerarSaida(Modelo):
    formularios: list[RascunhoGeradoSaida]


class ResumoSaida(Modelo):
    titulo: str
    paragrafos: list[str]
    destaques: list[str]
    total: int = Field(description="Quantos registros foram resumidos (calculado pelo código).")


# --- dependências ---


def obter_cliente() -> ClienteDeLLM:
    # Lê o ambiente a cada chamada: a chave pode ser definida sem reiniciar o app.
    return criar_cliente(os.environ)


DepCliente = Annotated[ClienteDeLLM, Depends(obter_cliente)]

roteador = APIRouter(
    dependencies=[Depends(esquema_do_token)], responses={**ERROS_COMUNS, **_ERROS_DA_IA}
)


# --- rotas ---


@roteador.post(
    "/definicoes/gerar",
    response_model=GerarSaida,
    tags=["ia"],
    summary="Propõe formulários a partir de um pedido em texto",
    description=(
        "Nunca salva: devolve rascunhos validados pelo mesmo código da publicação. Rascunho com "
        "`erros` segue para o construtor para a pessoa corrigir. Aprovados, são publicados de uma "
        "vez por `POST /formularios/lote`."
    ),
)
def gerar_formularios(
    entrada: GerarEntrada, conexao: DepConexao, cliente: DepCliente
) -> GerarSaida:
    rascunhos = [servico.Rascunho(f.nome, f.definicao) for f in entrada.rascunhos]
    gerados = gerador.gerar(conexao, cliente, entrada.pedido, rascunhos)
    return GerarSaida(
        formularios=[
            RascunhoGeradoSaida(
                nome=g.nome, definicao=g.definicao, erros=[ErroDeCampoSaida.de(e) for e in g.erros]
            )
            for g in gerados
        ]
    )


@roteador.post(
    "/formularios/{formulario_id}/resumo",
    response_model=ResumoSaida,
    tags=["ia"],
    summary="Resume os registros de uma versão com a IA",
    description=(
        "Mesma versão e mesmos filtros da listagem. O código calcula os agregados e a IA só "
        "redige; se algum número do texto não bater com eles, o resumo é descartado (502)."
    ),
)
def resumir_registros(
    formulario_id: int,
    conexao: DepConexao,
    cliente: DepCliente,
    versao_id: int | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> ResumoSaida:
    gerado = resumo.resumir(
        conexao,
        cliente,
        formulario_id,
        versao_id=versao_id,
        filtros=ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
    )
    texto = gerado.resumo
    return ResumoSaida(
        titulo=texto.titulo,
        paragrafos=list(texto.paragrafos),
        destaques=list(texto.destaques),
        total=gerado.agregados.total,
    )


# --- erros ---


async def _ia_indisponivel(_: Request, erro: Exception) -> Response:
    # A mensagem já é para a pessoa (PT-BR) e nunca contém a chave.
    return resposta_de_erro(503, str(erro))


async def _resposta_invalida(_: Request, erro: Exception) -> Response:
    return resposta_de_erro(
        502,
        "A IA respondeu fora do formato esperado. Tente de novo ou use o construtor manual.",
    )


async def _resumo_rejeitado(_: Request, erro: Exception) -> Response:
    assert isinstance(erro, ResumoRejeitado)
    return resposta_de_erro(
        502,
        "O resumo da IA foi descartado porque os números não conferem com os dados. Tente de novo.",
        [ErroDeCampoSaida(campo="resumo", mensagem=motivo) for motivo in erro.motivos],
    )


EXTENSAO = Extensao(
    nome="ia",
    roteador=roteador,
    tratadores={
        IaIndisponivel: _ia_indisponivel,
        RespostaDaIaInvalida: _resposta_invalida,
        ResumoRejeitado: _resumo_rejeitado,
    },
)
