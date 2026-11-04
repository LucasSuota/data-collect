"""Rota do assistente de procedimentos (RAG) da API (AGENTS.md §2.5).

Extensão opcional, como a de `ia/`. Sem chave ou sem internet o assistente não falha: mostra só
os trechos encontrados (fallback), e sem os embeddings a busca é só o BM25.
"""

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from forms.api_dependencias import DepConexao, autorizar
from forms.api_esquemas import Modelo
from forms.api_extensoes import Extensao
from forms.api_rotas import ERROS_COMUNS
from forms.ia.cliente import ClienteDeLLM, IaIndisponivel, criar_cliente
from forms.rag.chunker import Trecho, carregar_documentos
from forms.rag.indice import Buscador, IndiceBm25
from forms.rag.responder import perguntar
from forms.rag.semantico import IndiceHibrido, IndiceSemantico, carregar_vetores
from forms.servico import Conexao

PERGUNTA_MAXIMA = 1000


# --- modelos ---


class PerguntaEntrada(Modelo):
    pergunta: str = Field(min_length=1, max_length=PERGUNTA_MAXIMA)


class TrechoSaida(Modelo):
    arquivo: str = Field(description="Arquivo de origem, relativo à pasta de procedimentos.")
    titulo: str = Field(description="Caminho dos títulos: 'Moldagem > Cura'.")
    texto: str
    pontuacao: float


class RespostaSaida(Modelo):
    encontrou: bool
    texto: str | None = Field(
        description="Resposta redigida pela IA; nulo quando só há os trechos para mostrar."
    )
    usou_ia: bool
    trechos: list[TrechoSaida]


# --- dependências ---


def obter_cliente_opcional() -> ClienteDeLLM | None:
    try:
        return criar_cliente(os.environ)
    except IaIndisponivel:
        return None  # sem chave: o assistente segue, mostrando só os trechos


def localizar_docs(
    ambiente: Mapping[str, str],
    empacotado: bool | None = None,
    base_do_executavel: Path | None = None,
) -> Path | None:
    """Onde estão os procedimentos `.md`: a variável, o executável empacotado ou o repositório."""
    if (explicito := ambiente.get("FORMS_DOCS_DIR")) is not None:
        candidato = Path(explicito)
    else:
        if empacotado is None:
            empacotado = bool(getattr(sys, "frozen", False))
        if empacotado:
            base = base_do_executavel or Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            candidato = base / "docs"
        else:
            candidato = Path(__file__).resolve().parents[3] / "docs"
    return candidato if candidato.is_dir() else None


def obter_pasta_de_docs() -> Path | None:
    return localizar_docs(os.environ)


DepClienteOpcional = Annotated[ClienteDeLLM | None, Depends(obter_cliente_opcional)]
DepPastaDeDocs = Annotated[Path | None, Depends(obter_pasta_de_docs)]

roteador = APIRouter(dependencies=[Depends(autorizar)], responses=ERROS_COMUNS)


# --- rota ---


@roteador.post(
    "/assistente/perguntar",
    response_model=RespostaSaida,
    tags=["assistente"],
    summary="Responde a uma pergunta só com os procedimentos",
    description=(
        "Busca nos procedimentos (BM25, mais busca semântica se houver provedor de embeddings) "
        "e a IA redige a resposta só com os trechos recuperados. Sem base nos documentos, "
        "responde que não encontrou. Sem IA, devolve só os trechos."
    ),
)
def perguntar_aos_procedimentos(
    entrada: PerguntaEntrada,
    conexao: DepConexao,
    cliente: DepClienteOpcional,
    pasta: DepPastaDeDocs,
) -> RespostaSaida:
    trechos = carregar_documentos(pasta) if pasta is not None else []
    resposta = perguntar(_montar_indice(conexao, cliente, trechos), entrada.pergunta, cliente)
    return RespostaSaida(
        encontrou=resposta.encontrou,
        texto=resposta.texto,
        usou_ia=resposta.usou_ia,
        trechos=[
            TrechoSaida(
                arquivo=r.trecho.arquivo,
                titulo=r.trecho.titulo,
                texto=r.trecho.texto,
                pontuacao=r.pontuacao,
            )
            for r in resposta.trechos
        ],
    )


def _montar_indice(
    conexao: Conexao, cliente: ClienteDeLLM | None, trechos: list[Trecho]
) -> Buscador:
    bm25 = IndiceBm25(trechos)
    if cliente is None or cliente.modelo_de_vetores is None or not trechos:
        return bm25
    try:
        vetores = carregar_vetores(conexao, cliente, trechos)
        return IndiceHibrido(bm25, IndiceSemantico(trechos, vetores), cliente)
    except (IaIndisponivel, ValueError):
        return bm25  # sem embeddings agora: o BM25 sozinho responde


EXTENSAO = Extensao(nome="rag", roteador=roteador)
