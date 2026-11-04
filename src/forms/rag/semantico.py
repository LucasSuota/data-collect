"""Busca semântica opcional por embeddings, em Python puro (AGENTS.md §2.5 e §3.2).

Os vetores ficam numa tabela do SQLite (BLOB) e são comparados por cosseno em Python, sem
extensão de banco: com algumas centenas de trechos isso é instantâneo. O BM25 continua sendo a
base e o fallback: sem provedor de embeddings, sem internet ou sem chave, vale só ele.
"""

import hashlib
import math
import struct
from collections.abc import Sequence

from forms import repositorio
from forms.banco import Conexao
from forms.ia.cliente import ClienteDeLLM, IaIndisponivel
from forms.rag.chunker import Trecho
from forms.rag.indice import IndiceBm25, ResultadoDeBusca
from forms.servico_base import transacao

# Cosseno mínimo para um trecho contar como relacionado. Sem isso, "o vizinho mais próximo"
# sempre apareceria e a resposta "não encontrei" nunca existiria. O valor depende do modelo de
# embeddings: 0,3 é um ponto de partida conservador, a ajustar com perguntas reais.
LIMIAR_DE_SIMILARIDADE = 0.3
# Constante clássica do RRF (Cormack et al., 2009): suaviza o peso das primeiras posições.
CONSTANTE_RRF = 60
# Quantos candidatos cada busca entrega à fusão, antes de cortar nos `k` finais.
CANDIDATOS_POR_BUSCA = 10


def texto_para_vetorizar(trecho: Trecho) -> str:
    # O título entra, como no BM25: "Cura" dá contexto a "Manter úmido por 7 dias".
    return f"{trecho.titulo}\n{trecho.texto}"


def empacotar(vetor: Sequence[float]) -> bytes:
    """float32 little-endian, 4 bytes por dimensão (a ordem fixa vale em qualquer máquina)."""
    return struct.pack(f"<{len(vetor)}f", *vetor)


def desempacotar(blob: bytes) -> list[float]:
    if len(blob) % 4:
        raise ValueError("O tamanho do vetor guardado deve ser múltiplo de 4 bytes.")
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def similaridade_de_cosseno(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vetores com dimensões diferentes ({len(a)} e {len(b)}).")
    norma = math.sqrt(math.sumprod(a, a)) * math.sqrt(math.sumprod(b, b))
    if norma == 0:
        return 0.0  # vetor nulo não aponta para lugar nenhum
    return max(-1.0, min(1.0, math.sumprod(a, b) / norma))


class IndiceSemantico:
    def __init__(self, trechos: Sequence[Trecho], vetores: Sequence[Sequence[float]]) -> None:
        if len(trechos) != len(vetores):
            raise ValueError("É preciso um vetor por trecho.")
        if len({len(v) for v in vetores}) > 1:
            raise ValueError("Os vetores dos trechos têm dimensões diferentes.")
        self._trechos = list(trechos)
        self._vetores = [list(v) for v in vetores]

    def buscar(
        self, vetor_da_consulta: Sequence[float], k: int = 3, limiar: float = LIMIAR_DE_SIMILARIDADE
    ) -> list[ResultadoDeBusca]:
        pontuados = [
            (similaridade_de_cosseno(vetor_da_consulta, vetor), posicao)
            for posicao, vetor in enumerate(self._vetores)
        ]
        # Pontuação decrescente; em empate, a ordem original dos documentos (como no BM25).
        pontuados.sort(key=lambda par: (-par[0], par[1]))
        return [
            ResultadoDeBusca(self._trechos[pos], pont)
            for pont, pos in pontuados[:k]
            if pont >= limiar
        ]


def carregar_vetores(
    conexao: Conexao, cliente: ClienteDeLLM, trechos: Sequence[Trecho]
) -> list[list[float]]:
    """Os vetores dos trechos, na ordem dada. Só o que ainda não está no banco é vetorizado.

    Levanta `IaIndisponivel` se não houver provedor, se ele falhar ou se a resposta for inválida;
    nesse caso nada é gravado e quem chama usa só o BM25.
    """
    modelo = cliente.modelo_de_vetores
    if modelo is None:
        raise IaIndisponivel("Não há provedor de embeddings configurado; a busca usa só o BM25.")

    chaves = [_chave(modelo, trecho) for trecho in trechos]
    guardados = repositorio.listar_vetores(conexao)
    faltando = {c: t for c, t in zip(chaves, trechos, strict=True) if c not in guardados}

    novos: dict[str, bytes] = {}
    if faltando:
        # A chamada de rede fica fora da transação, para não segurar o banco enquanto espera.
        textos = [texto_para_vetorizar(t) for t in faltando.values()]
        vetores = cliente.vetorizar(textos)
        _conferir_resposta(vetores, len(textos))
        novos = {c: empacotar(v) for c, v in zip(faltando, vetores, strict=True)}

    obsoletos = guardados.keys() - set(chaves)
    if novos or obsoletos:
        with transacao(conexao):
            repositorio.guardar_vetores(conexao, novos)
            repositorio.apagar_vetores(conexao, obsoletos)

    todos = {**guardados, **novos}
    # Sempre o que está em bytes (float32), para a 1ª e a 2ª chamada darem o mesmo resultado.
    return [desempacotar(todos[chave]) for chave in chaves]


def fundir_por_rrf(
    listas: Sequence[Sequence[ResultadoDeBusca]], k: int, constante: int = CONSTANTE_RRF
) -> list[ResultadoDeBusca]:
    """Reciprocal Rank Fusion: pontuação = Σ 1 / (constante + posição), posição a partir de 1.

    Funde só pelas posições, então pontuações de escalas diferentes (BM25 e cosseno) não precisam
    ser normalizadas. Em empate vale a ordem em que o trecho apareceu pela primeira vez.
    """
    somas: dict[Trecho, float] = {}
    for lista in listas:
        for posicao, resultado in enumerate(lista, start=1):
            somas[resultado.trecho] = somas.get(resultado.trecho, 0.0) + 1 / (constante + posicao)
    ordenados = sorted(somas.items(), key=lambda par: -par[1])  # estável: empate mantém a ordem
    return [ResultadoDeBusca(trecho, soma) for trecho, soma in ordenados[:k]]


class IndiceHibrido:
    """BM25 + semântico fundidos por RRF; sem embeddings da consulta, devolve só o BM25."""

    def __init__(self, bm25: IndiceBm25, semantico: IndiceSemantico, cliente: ClienteDeLLM) -> None:
        self._bm25 = bm25
        self._semantico = semantico
        self._cliente = cliente

    def buscar(self, consulta: str, k: int = 3) -> list[ResultadoDeBusca]:
        por_palavras = self._bm25.buscar(consulta, CANDIDATOS_POR_BUSCA)
        try:
            (vetor,) = self._cliente.vetorizar([consulta])
            _conferir_resposta([vetor], 1)
            por_significado = self._semantico.buscar(vetor, CANDIDATOS_POR_BUSCA)
        except (IaIndisponivel, ValueError):
            # Sem internet, sem chave ou vetor incompatível: o BM25 sozinho continua respondendo.
            return por_palavras[:k]
        return fundir_por_rrf([por_palavras, por_significado], k)


def _chave(modelo: str, trecho: Trecho) -> str:
    texto = f"{modelo}\0{trecho.arquivo}\0{texto_para_vetorizar(trecho)}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _conferir_resposta(vetores: Sequence[Sequence[float]], esperados: int) -> None:
    """A saída do provedor é dado não confiável: quantidade, tamanho e valores são conferidos."""
    if len(vetores) != esperados:
        raise IaIndisponivel(f"O provedor devolveu {len(vetores)} vetores para {esperados} textos.")
    dimensoes = {len(v) for v in vetores}
    if (
        len(dimensoes) != 1
        or 0 in dimensoes
        or not all(math.isfinite(x) for v in vetores for x in v)
    ):
        raise IaIndisponivel("O provedor de embeddings devolveu vetores inválidos.")
