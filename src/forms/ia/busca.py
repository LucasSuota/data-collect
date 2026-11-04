"""Busca híbrida sobre os documentos da equipe (AGENTS.md §2.5).

Ordem fixa: (1) **filtros de metadados no SQL** (equipe, formulário, datas), sempre primeiro;
(2) **BM25 escrito à mão** sobre o que sobrou; (3) vetores com **pgvector**, só entre os
candidatos, se o provedor tem embeddings; (4) fusão por **RRF** (*reciprocal rank fusion*): cada
lista dá `1 / (60 + posição)` ao documento, e as notas se somam. Sem embeddings vale só 1 + 2.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from forms.banco import Conexao
from forms.ia import repositorio
from forms.ia.cliente import IaIndisponivel, ProvedorDeLLM
from forms.ia.repositorio import DocumentoGravado
from forms.rag.chunker import Trecho
from forms.rag.indice import IndiceBm25

LIMITE_DE_CANDIDATOS = 2000
CONSTANTE_RRF = 60


@dataclass(frozen=True)
class Achado:
    documento: DocumentoGravado
    pontuacao: float


def buscar(
    conexao: Conexao,
    cliente: ProvedorDeLLM | None,
    consulta: str,
    *,
    formulario_id: int | None = None,
    de: date | None = None,
    ate: date | None = None,
    k: int = 5,
) -> list[Achado]:
    candidatos = repositorio.candidatos(
        conexao,
        formulario_id=formulario_id,
        de=None if de is None else datetime.combine(de, time.min, UTC).isoformat(),
        ate=None if ate is None else datetime.combine(ate, time.max, UTC).isoformat(),
        limite=LIMITE_DE_CANDIDATOS,
    )
    if not candidatos:
        return []
    por_id = {d.id: d for d in candidatos}

    trechos = [
        Trecho(str(d.id), str(d.metadados.get("formulario", "")), d.texto) for d in candidatos
    ]
    por_bm25 = [int(r.trecho.arquivo) for r in IndiceBm25(trechos).buscar(consulta, k=k * 3)]
    por_vetor = _por_vetor(conexao, cliente, consulta, por_id.keys(), k * 3)

    notas: dict[int, float] = {}
    for ranking in (por_bm25, por_vetor):
        for posicao, documento_id in enumerate(ranking):
            notas[documento_id] = notas.get(documento_id, 0.0) + 1 / (CONSTANTE_RRF + posicao + 1)
    melhores = sorted(notas.items(), key=lambda par: (-par[1], par[0]))[:k]
    return [Achado(por_id[id_], nota) for id_, nota in melhores]


def _por_vetor(
    conexao: Conexao, cliente: ProvedorDeLLM | None, consulta: str, ids, k: int
) -> list[int]:
    if cliente is None or cliente.modelo_de_vetores is None:
        return []
    try:
        vetor = cliente.vetorizar([consulta])[0]
    except IaIndisponivel:
        return []  # sem embeddings agora: o BM25 sozinho responde
    proximos = repositorio.mais_proximos(conexao, cliente.modelo_de_vetores, vetor, ids, k)
    return [documento_id for documento_id, _ in proximos]
