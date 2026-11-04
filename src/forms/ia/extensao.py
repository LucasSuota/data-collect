"""Rotas de IA da API: gerador de formulários e resumo de registros (AGENTS.md §2.5).

É uma extensão opcional: o núcleo a encontra pelo nome (`api_extensoes.py`) e o app funciona sem
esta pasta. Aqui só há HTTP; a regra está em `gerador.py`, `resumo.py` e `validacao.py`.
Nenhuma rota grava nada: o gerador devolve rascunhos e o resumo só lê.
"""

import json
import os
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import Field

from forms import servico
from forms.api_dependencias import DepAgora, DepConexao, autorizar
from forms.api_esquemas import ErroDeCampoSaida, ErroSaida, FormularioEntrada, Modelo
from forms.api_extensoes import Extensao, resposta_de_erro
from forms.api_rotas import ERROS_COMUNS, ler_filtros
from forms.ia import chat, configuracao, gerador, indexacao, resumo
from forms.ia import repositorio as ia_repositorio
from forms.ia.cliente import ClienteDeLLM, IaIndisponivel
from forms.ia.gerador import MAXIMO_DE_FORMULARIOS, PEDIDO_MAXIMO, RespostaDaIaInvalida
from forms.ia.validacao import ResumoRejeitado
from forms.segredos import Cifra

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


def obter_cifra() -> Cifra | None:
    return configuracao.cifra_da_instancia()


DepCifra = Annotated[Cifra | None, Depends(obter_cifra)]


def obter_cliente(conexao: DepConexao, cifra: DepCifra) -> ClienteDeLLM:
    """O provedor da **equipe** (§2.5). IA desligada na equipe → 503 com a mensagem."""
    return configuracao.criar_cliente_da_equipe(conexao, cifra)


def obter_cliente_opcional_da_equipe(conexao: DepConexao, cifra: DepCifra) -> ClienteDeLLM | None:
    """Como `obter_cliente`, mas sem IA o chat segue só com os trechos e resultados."""
    try:
        return configuracao.criar_cliente_da_equipe(conexao, cifra)
    except IaIndisponivel:
        return None


DepCliente = Annotated[ClienteDeLLM, Depends(obter_cliente)]
DepClienteDoChat = Annotated[ClienteDeLLM | None, Depends(obter_cliente_opcional_da_equipe)]

roteador = APIRouter(dependencies=[Depends(autorizar)], responses={**ERROS_COMUNS, **_ERROS_DA_IA})


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


# --- configuração da IA da equipe (§2.5, §2.15) ---


class ConfigSaida(Modelo):
    """A configuração, sem a chave: só `chave_definida` (§12)."""

    ativa: bool
    provedor: Literal["anthropic", "openai_compativel"]
    base_url: str | None
    modelo: str | None
    modelo_embeddings: str | None
    chave_definida: bool
    consentimento_por: int | None
    consentimento_em: str | None
    modelos_de_vetor_disponiveis: bool = Field(
        description="Há um modelo de embeddings configurado (busca por vetores)."
    )


class ConfigEntrada(Modelo):
    ativa: bool
    aceite_do_aviso: bool = Field(
        default=False,
        description="Obrigatório ao ligar a IA: a pessoa leu para onde os dados vão (§2.15).",
    )
    provedor: Literal["anthropic", "openai_compativel"]
    base_url: str | None = Field(default=None, max_length=300)
    modelo: str | None = Field(default=None, max_length=120)
    modelo_embeddings: str | None = Field(default=None, max_length=120)
    chave: str | None = Field(
        default=None,
        max_length=500,
        description="Omitida mantém a atual; vazia remove; preenchida troca. Nunca volta.",
    )


class TesteSaida(Modelo):
    ok: bool
    mensagem: str


class ReindexacaoSaida(Modelo):
    gravados: int
    removidos: int
    iguais: int
    vetorizados: int


class UsoSaida(Modelo):
    chamadas_da_pessoa: int
    chamadas_da_equipe: int
    tokens_da_equipe: int
    limite_de_chamadas_por_pessoa: int
    limite_de_chamadas_por_equipe: int
    limite_de_tokens_por_equipe: int


def _config_saida(conexao: DepConexao) -> ConfigSaida:
    c = configuracao.obter(conexao)
    return ConfigSaida(
        ativa=c.ativa,
        provedor=c.provedor,  # type: ignore[arg-type]  # o Pydantic confere o `Literal`
        base_url=c.base_url,
        modelo=c.modelo,
        modelo_embeddings=c.modelo_embeddings,
        chave_definida=c.chave_definida,
        consentimento_por=c.consentimento_por,
        consentimento_em=c.consentimento_em,
        modelos_de_vetor_disponiveis=c.modelo_embeddings is not None,
    )


@roteador.get(
    "/ia",
    response_model=ConfigSaida,
    tags=["ia"],
    summary="Configuração da IA desta equipe (sem a chave)",
)
def obter_configuracao(conexao: DepConexao) -> ConfigSaida:
    return _config_saida(conexao)


@roteador.put(
    "/ia",
    response_model=ConfigSaida,
    tags=["ia"],
    summary="Liga, desliga ou configura a IA da equipe",
    description=(
        "Ligar exige `aceite_do_aviso`. A chave é cifrada antes de ir ao banco e nunca volta."
    ),
)
def gravar_configuracao(
    entrada: ConfigEntrada, conexao: DepConexao, cifra: DepCifra, agora: DepAgora
) -> ConfigSaida:
    configuracao.atualizar(
        conexao,
        cifra,
        ativa=entrada.ativa,
        aceite_do_aviso=entrada.aceite_do_aviso,
        provedor=entrada.provedor,
        base_url=entrada.base_url,
        modelo=entrada.modelo,
        modelo_embeddings=entrada.modelo_embeddings,
        chave=entrada.chave,
        agora=agora,
    )
    return _config_saida(conexao)


@roteador.post(
    "/ia/testar",
    response_model=TesteSaida,
    tags=["ia"],
    summary="Faz uma chamada mínima ao provedor para conferir a configuração",
)
def testar_configuracao(conexao: DepConexao, cifra: DepCifra, agora: DepAgora) -> TesteSaida:
    try:
        cliente = configuracao.criar_cliente_da_equipe(conexao, cifra)
        cliente.completar("Responda apenas: ok", "ok", maximo_de_tokens=8)
    except IaIndisponivel as erro:
        return TesteSaida(ok=False, mensagem=str(erro))
    return TesteSaida(ok=True, mensagem="Conexão com o provedor funcionando.")


@roteador.post(
    "/ia/reindexar",
    response_model=ReindexacaoSaida,
    tags=["ia"],
    summary="Reindexa registros e definições da equipe para o assistente",
)
def reindexar(conexao: DepConexao, cliente: DepClienteDoChat, agora: DepAgora) -> ReindexacaoSaida:
    ia_repositorio.apagar_todos_os_documentos(conexao)
    resultado = indexacao.sincronizar(conexao, agora)
    vetorizados = indexacao.vetorizar_pendentes(conexao, cliente) if cliente is not None else 0
    return ReindexacaoSaida(
        gravados=resultado.gravados,
        removidos=resultado.removidos,
        iguais=resultado.iguais,
        vetorizados=vetorizados,
    )


@roteador.get(
    "/ia/uso",
    response_model=UsoSaida,
    tags=["ia"],
    summary="Uso da IA nas últimas 24 horas (só contagens)",
)
def uso_da_ia(conexao: DepConexao, agora: DepAgora) -> UsoSaida:
    desde = agora - timedelta(days=1)
    pessoa = ia_repositorio.uso_desde(conexao, desde, so_da_pessoa=True)
    equipe = ia_repositorio.uso_desde(conexao, desde, so_da_pessoa=False)
    return UsoSaida(
        chamadas_da_pessoa=pessoa.chamadas,
        chamadas_da_equipe=equipe.chamadas,
        tokens_da_equipe=equipe.tokens,
        limite_de_chamadas_por_pessoa=chat.LIMITE_DE_CHAMADAS_POR_PESSOA_E_DIA,
        limite_de_chamadas_por_equipe=chat.LIMITE_DE_CHAMADAS_POR_EQUIPE_E_DIA,
        limite_de_tokens_por_equipe=chat.LIMITE_DE_TOKENS_POR_EQUIPE_E_DIA,
    )


# --- chatbot (§2.5) ---


class ChatEntrada(Modelo):
    mensagem: str = Field(min_length=1, max_length=chat.PERGUNTA_MAXIMA)
    conversa_id: int | None = Field(default=None, description="Omitida: começa uma conversa nova.")


class ConversaSaida(Modelo):
    id: int
    titulo: str
    criada_em: str


class MensagemSaida(Modelo):
    id: int
    papel: Literal["pessoa", "assistente"]
    texto: str
    citacoes: list[dict[str, object]]
    criada_em: str


class ConversaComMensagensSaida(Modelo):
    conversa: ConversaSaida
    mensagens: list[MensagemSaida]


def obter_pasta_de_ajuda() -> Path | None:
    from forms.rag.extensao import localizar_ajuda  # noqa: PLC0415 - o módulo `rag` é opcional

    return localizar_ajuda(os.environ)


DepPastaDeAjuda = Annotated[Path | None, Depends(obter_pasta_de_ajuda)]


@roteador.post(
    "/chat",
    tags=["ia"],
    summary="Pergunta ao assistente (resposta em fluxo, SSE)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Eventos SSE."}},
    description=(
        "Eventos `data: {json}`: `conversa`, vários `texto` e um `fim` com `encontrou`, "
        "`usou_ia` e `citacoes`. A resposta é redigida só com o que o código recuperou e todo "
        "número é conferido antes de ser mostrado."
    ),
)
def conversar(
    entrada: ChatEntrada,
    conexao: DepConexao,
    cliente: DepClienteDoChat,
    pasta: DepPastaDeAjuda,
    agora: DepAgora,
) -> StreamingResponse:
    # Tudo é calculado **antes** de abrir o fluxo: a conexão do banco volta ao pool quando a
    # rota termina, e o fluxo só repassa texto já pronto e já conferido.
    conversa_id = entrada.conversa_id
    if conversa_id is None:
        conversa_id = ia_repositorio.criar_conversa(conexao, entrada.mensagem, agora)
    else:
        ia_repositorio.conversa_da_pessoa(conexao, conversa_id)
    resposta = chat.responder(conexao, cliente, entrada.mensagem, agora=agora, pasta_de_ajuda=pasta)
    ia_repositorio.adicionar_mensagem(conexao, conversa_id, "pessoa", entrada.mensagem, [], agora)
    ia_repositorio.adicionar_mensagem(
        conexao, conversa_id, "assistente", resposta.texto, list(resposta.citacoes), agora
    )

    def eventos() -> Iterator[str]:
        yield _sse({"tipo": "conversa", "conversa_id": conversa_id})
        for inicio in range(0, len(resposta.texto), 24):
            yield _sse({"tipo": "texto", "texto": resposta.texto[inicio : inicio + 24]})
        yield _sse(
            {
                "tipo": "fim",
                "encontrou": resposta.encontrou,
                "usou_ia": resposta.usou_ia,
                "ia_disponivel": cliente is not None,
                "citacoes": list(resposta.citacoes),
            }
        )

    return StreamingResponse(
        eventos(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


def _sse(dado: dict[str, object]) -> str:
    return f"data: {json.dumps(dado, ensure_ascii=False)}\n\n"


@roteador.get(
    "/chat/conversas",
    response_model=list[ConversaSaida],
    tags=["ia"],
    summary="Minhas conversas com o assistente",
)
def listar_conversas(conexao: DepConexao) -> list[ConversaSaida]:
    return [
        ConversaSaida(id=c.id, titulo=c.titulo, criada_em=c.criada_em)
        for c in ia_repositorio.listar_conversas(conexao)
    ]


@roteador.get(
    "/chat/conversas/{conversa_id}",
    response_model=ConversaComMensagensSaida,
    tags=["ia"],
    summary="Uma conversa com as mensagens",
)
def obter_conversa(conversa_id: int, conexao: DepConexao) -> ConversaComMensagensSaida:
    conversa = ia_repositorio.conversa_da_pessoa(conexao, conversa_id)
    return ConversaComMensagensSaida(
        conversa=ConversaSaida(
            id=conversa.id, titulo=conversa.titulo, criada_em=conversa.criada_em
        ),
        mensagens=[
            MensagemSaida(
                id=m.id,
                papel=m.papel,  # type: ignore[arg-type]  # o Pydantic confere o `Literal`
                texto=m.texto,
                citacoes=[c for c in m.citacoes if isinstance(c, dict)],
                criada_em=m.criada_em,
            )
            for m in ia_repositorio.listar_mensagens(conexao, conversa_id)
        ],
    )


@roteador.delete(
    "/chat/conversas/{conversa_id}",
    status_code=204,
    response_class=Response,
    tags=["ia"],
    summary="Apaga uma conversa (LGPD)",
)
def apagar_conversa(conversa_id: int, conexao: DepConexao) -> Response:
    ia_repositorio.apagar_conversa(conexao, conversa_id)
    return Response(status_code=204)


# --- erros ---


async def _config_invalida(_: Request, erro: Exception) -> Response:
    assert isinstance(erro, configuracao.ConfigInvalida)
    return resposta_de_erro(
        422, "Configuração inválida.", [ErroDeCampoSaida.de(e) for e in erro.erros]
    )


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
        configuracao.ConfigInvalida: _config_invalida,
        RespostaDaIaInvalida: _resposta_invalida,
        ResumoRejeitado: _resumo_rejeitado,
    },
)
