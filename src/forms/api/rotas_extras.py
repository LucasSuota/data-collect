"""Endpoints de início, busca, notificações, tour, exemplos e dados da pessoa (§2.15 a §2.18).

Só traduz HTTP: a regra está em `servicos/extras.py` e `servico.py`. A permissão de cada rota vem
da matriz única (`api/matriz_permissoes.py`).
"""

import dataclasses
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from forms.api.dependencias import DepAgora, DepConexao, DepIdentidade, autorizar
from forms.api.esquemas import (
    BuscaFormularioSaida,
    BuscaRegistroSaida,
    BuscaSaida,
    DestaqueSaida,
    ErroSaida,
    ExemploSaida,
    ExemplosImportadosSaida,
    ImportarExemplosEntrada,
    NotificacaoSaida,
    NotificacoesSaida,
    ProgressoEntrada,
    ProgressoSaida,
    ProntoSaida,
    RegistroRecenteSaida,
)
from forms.api.rotas_formularios import ERROS_COMUNS
from forms.infra import banco
from forms.servicos import servico

roteador = APIRouter(dependencies=[Depends(autorizar)], responses=ERROS_COMUNS)
roteador_aberto = APIRouter(tags=["público"])


def _pessoa(conexao: DepConexao) -> int:
    usuario_id = conexao.usuario_id
    assert usuario_id is not None  # a dependência `autorizar` identifica a pessoa
    return usuario_id


# --- busca e início ---


@roteador.get(
    "/busca",
    response_model=BuscaSaida,
    tags=["busca"],
    summary="Busca global: formulários e registros (sem IA)",
    description="Nome de formulário, `#id` e texto/seleção dos registros; só o que o cargo vê.",
)
def buscar(conexao: DepConexao, q: Annotated[str, Query(max_length=100)]) -> BuscaSaida:
    resultado = servico.buscar(conexao, q)
    return BuscaSaida(
        formularios=[BuscaFormularioSaida(id=f.id, nome=f.nome) for f in resultado.formularios],
        registros=[
            BuscaRegistroSaida(id=r, formulario_id=f, formulario=nome)
            for r, f, nome in resultado.registros
        ],
    )


@roteador.get(
    "/registros/recentes",
    response_model=list[RegistroRecenteSaida],
    tags=["registros"],
    summary="Os últimos registros alterados, com estado e valor em destaque",
)
def registros_recentes(
    conexao: DepConexao, limite: Annotated[int, Query(ge=1, le=20)] = 5
) -> list[RegistroRecenteSaida]:
    return [
        RegistroRecenteSaida(
            id=r.registro.id,
            formulario_id=r.registro.formulario_id,
            formulario=r.formulario,
            atualizado_em=r.registro.atualizado_em,
            estado=r.estado,  # type: ignore[arg-type]  # o Pydantic confere o `Literal`
            destaque=None
            if r.destaque is None
            else DestaqueSaida(rotulo=r.destaque[0], valor=r.destaque[1], unidade=r.destaque[2]),
        )
        for r in servico.recentes_com_estado(conexao, limite)
    ]


# --- notificações ---


@roteador.get(
    "/notificacoes",
    response_model=NotificacoesSaida,
    tags=["notificações"],
    summary="Minhas notificações (só dentro do app)",
)
def notificacoes(conexao: DepConexao) -> NotificacoesSaida:
    itens, nao_lidas = servico.listar_notificacoes(conexao)
    return NotificacoesSaida(
        itens=[
            NotificacaoSaida(
                id=n.id,
                tipo=n.tipo,  # type: ignore[arg-type]  # o Pydantic confere o `Literal`
                referencia=dict(n.referencia),
                lida=n.lida,
                criada_em=n.criada_em,
            )
            for n in itens
        ],
        nao_lidas=nao_lidas,
    )


@roteador.post(
    "/notificacoes/{notificacao_id}/lida",
    status_code=204,
    response_class=Response,
    tags=["notificações"],
    summary="Marca a notificação como lida",
)
def marcar_lida(notificacao_id: int, conexao: DepConexao, agora: DepAgora) -> Response:
    servico.marcar_notificacao_lida(conexao, notificacao_id, agora)
    return Response(status_code=204)


# --- tour e primeiros passos ---


@roteador.get(
    "/eu/onboarding", response_model=ProgressoSaida, tags=["pessoa"], summary="Progresso do tour"
)
def obter_onboarding(conexao: DepConexao) -> ProgressoSaida:
    return ProgressoSaida(**dataclasses.asdict(servico.obter_progresso(conexao, _pessoa(conexao))))


@roteador.put(
    "/eu/onboarding",
    response_model=ProgressoSaida,
    tags=["pessoa"],
    summary="Grava o progresso do tour (por pessoa, no servidor)",
)
def gravar_onboarding(
    entrada: ProgressoEntrada, conexao: DepConexao, agora: DepAgora
) -> ProgressoSaida:
    progresso = servico.atualizar_progresso(
        conexao,
        _pessoa(conexao),
        tour_concluido=entrada.tour_concluido,
        passo=entrada.passo,
        checklist_dispensado=entrada.checklist_dispensado,
        agora=agora,
    )
    return ProgressoSaida(**dataclasses.asdict(progresso))


# --- exemplos (galeria "Começar com um exemplo") ---


@roteador.get(
    "/templates",
    response_model=list[ExemploSaida],
    tags=["exemplos"],
    summary="Os exemplos de formulário que vêm com o app",
)
def listar_exemplos() -> list[ExemploSaida]:
    return [
        ExemploSaida(
            nome=e.nome, descricao=e.descricao, campos=e.campos, depende_de=list(e.depende_de)
        )
        for e in servico.listar_exemplos()
    ]


@roteador.post(
    "/templates/importar",
    status_code=201,
    response_model=ExemplosImportadosSaida,
    tags=["exemplos"],
    summary="Importa exemplos escolhidos, na ordem das dependências",
)
def importar_exemplos(
    entrada: ImportarExemplosEntrada, conexao: DepConexao, agora: DepAgora
) -> ExemplosImportadosSaida:
    criados = servico.importar_exemplos(conexao, entrada.nomes, agora)
    return ExemplosImportadosSaida(formularios=[c.formulario.nome for c in criados])


# --- direitos da pessoa (LGPD) ---


@roteador.get(
    "/eu/exportar",
    tags=["pessoa"],
    summary="Exporta tudo que o sistema guarda sobre mim (JSON)",
    response_class=JSONResponse,
    responses={200: {"description": "Perfil, aceites, equipes e o que a pessoa criou."}},
)
def exportar_meus_dados(conexao: DepConexao) -> JSONResponse:
    dados = servico.exportar_meus_dados(conexao, _pessoa(conexao))
    return JSONResponse(
        content=dados,
        headers={"Content-Disposition": 'attachment; filename="meus-dados.json"'},
    )


@roteador.delete(
    "/eu",
    status_code=204,
    response_class=Response,
    tags=["pessoa"],
    summary="Exclui minha conta (a autoria dos meus registros é anonimizada)",
    responses={422: {"model": ErroSaida, "description": "Única administradora de uma equipe."}},
)
def excluir_minha_conta(
    request: Request, conexao: DepConexao, identidade: DepIdentidade
) -> Response:
    servico.excluir_minha_conta(conexao, _pessoa(conexao))
    gestor = request.app.state.gestor
    if gestor is not None:
        gestor.apagar(identidade.sub)
    return Response(status_code=204)


# --- saúde ---


@roteador_aberto.get(
    "/readyz",
    response_model=ProntoSaida,
    summary="O app está pronto: banco acessível e esquema migrado",
    responses={503: {"model": ErroSaida, "description": "Banco inacessível ou sem migração."}},
)
def pronto(request: Request) -> ProntoSaida:
    pool = request.app.state.pool
    with pool.connection() as conexao:
        linha = conexao.execute(
            "SELECT COALESCE(MAX(numero), 0) AS n FROM esquema_versao"
        ).fetchone()
    migracao = int(linha["n"]) if linha else 0
    if migracao < max((m.numero for m in banco.migracoes_do_pacote()), default=0):
        raise banco.EsquemaDesatualizado("O banco ainda não recebeu todas as migrações.")
    return ProntoSaida(status="ok", migracao=migracao)
