"""BM25 escrito à mão, sem framework (AGENTS.md §2.5 e §3.2).

pontuação(d, q) = Σ idf(t) · tf(t,d)·(k1+1) / (tf(t,d) + k1·(1 − b + b·|d|/média))
idf(t) = ln(1 + (N − df(t) + 0,5) / (df(t) + 0,5))
"""

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from forms.rag.chunker import Trecho

# Palavras vazias do português mais comuns: sem elas, "de" e "o" dominariam a busca.
PALAVRAS_VAZIAS = frozenset(
    "a o as os um uma uns umas de do da dos das em no na nos nas por para com sem e ou que "
    "se ao aos à às é são foi ser há como mais mas já ele ela eles elas seu sua seus suas "
    "este esta estes estas isso isto esse essa qual quais quando onde".split()
)
_PALAVRA = re.compile(r"[a-z0-9]+")


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sem acento e sem palavras vazias: "Cálculo" e "calculo" são o mesmo termo."""
    sem_acento = (
        unicodedata.normalize("NFD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    )
    vazias = {_sem_acento(p) for p in PALAVRAS_VAZIAS}
    return [t for t in _PALAVRA.findall(sem_acento) if t not in vazias]


def _sem_acento(palavra: str) -> str:
    return unicodedata.normalize("NFD", palavra).encode("ascii", "ignore").decode("ascii")


@dataclass(frozen=True)
class ResultadoDeBusca:
    trecho: Trecho
    pontuacao: float


class IndiceBm25:
    def __init__(self, trechos: Sequence[Trecho], k1: float = 1.5, b: float = 0.75) -> None:
        self._trechos = list(trechos)
        self._k1, self._b = k1, b
        # O título entra na indexação: "Cura do concreto" ajuda a achar o trecho da cura.
        self._frequencias = [Counter(tokenizar(f"{t.titulo} {t.texto}")) for t in self._trechos]
        self._tamanhos = [sum(f.values()) for f in self._frequencias]
        self._media = sum(self._tamanhos) / len(self._tamanhos) if self._tamanhos else 0.0
        documentos_com_termo: Counter[str] = Counter()
        for frequencia in self._frequencias:
            documentos_com_termo.update(frequencia.keys())
        total = len(self._trechos)
        self._idf = {
            termo: math.log(1 + (total - df + 0.5) / (df + 0.5))
            for termo, df in documentos_com_termo.items()
        }

    def buscar(self, consulta: str, k: int = 3) -> list[ResultadoDeBusca]:
        termos = set(tokenizar(consulta))
        resultados = []
        for posicao, frequencia in enumerate(self._frequencias):
            pontuacao = self._pontuar(termos, frequencia, self._tamanhos[posicao])
            if pontuacao > 0:
                resultados.append((pontuacao, posicao))
        # Pontuação decrescente; em empate, a ordem original dos documentos.
        resultados.sort(key=lambda par: (-par[0], par[1]))
        return [ResultadoDeBusca(self._trechos[pos], pont) for pont, pos in resultados[:k]]

    def _pontuar(self, termos: set[str], frequencia: Counter[str], tamanho: int) -> float:
        pontuacao = 0.0
        for termo in termos:
            tf = frequencia.get(termo, 0)
            if tf == 0:
                continue
            normalizacao = 1 - self._b + self._b * tamanho / self._media
            pontuacao += self._idf[termo] * tf * (self._k1 + 1) / (tf + self._k1 * normalizacao)
        return pontuacao
