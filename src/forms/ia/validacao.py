"""Valida a saída do LLM antes de qualquer pessoa vê-la (AGENTS.md §2.5 e §12).

A saída é **dado não confiável**: precisa ter o formato esperado e **todo número do texto tem de
bater com o que o código calculou**. Se não bater, o resumo inteiro é rejeitado.
"""

import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from forms.dominio.models import ErroDeDominio

MAXIMO_DO_TITULO = 120
MAXIMO_DE_PARAGRAFOS = 6
MAXIMO_DO_PARAGRAFO = 800
MAXIMO_DE_DESTAQUES = 6
MAXIMO_DO_DESTAQUE = 200

# Sinal só no começo ou depois de espaço: o hífen de "2026-11-02" e de "10-20" não é sinal.
_NUMERO = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)*")
_MILHAR = re.compile(r"\d{1,3}(?:\.\d{3})+")


class ResumoRejeitado(ErroDeDominio):
    """A IA respondeu, mas o resumo não pode ser mostrado."""

    def __init__(self, motivos: list[str]) -> None:
        super().__init__("O resumo da IA foi rejeitado: " + "; ".join(motivos))
        self.motivos = tuple(motivos)


@dataclass(frozen=True)
class Resumo:
    titulo: str
    paragrafos: tuple[str, ...]
    destaques: tuple[str, ...]


def extrair_numeros(texto: str) -> list[tuple[Decimal, int]]:
    """Os números do texto em formato brasileiro, com quantas casas decimais foram escritas."""
    return [(valor, casas) for _, valor, casas in _numeros_com_texto(texto)]


def conferir_numeros(texto: str, permitidos: Collection[Decimal]) -> list[str]:
    """Os números escritos que NÃO batem com nenhum valor permitido.

    Bate se o valor, arredondado para as casas escritas (meio para cima, como o resto do
    sistema), é igual ao número: "25,5" confere com 25,4647...; "25,47" não.
    """
    return [
        bruto
        for bruto, valor, casas in _numeros_com_texto(texto)
        if not any(_arredondar(permitido, casas) == valor for permitido in permitidos)
    ]


def validar_resumo(saida: str, permitidos: Collection[Decimal]) -> Resumo:
    dados = _ler_json(saida)
    resumo = _montar(dados)
    erros = [
        f"o número {numero} não confere com os dados"
        for texto in (resumo.titulo, *resumo.paragrafos, *resumo.destaques)
        for numero in conferir_numeros(texto, permitidos)
    ]
    if erros:
        raise ResumoRejeitado(erros)
    return resumo


def _ler_json(saida: str) -> object:
    try:
        return json.loads(saida)
    except json.JSONDecodeError:
        inicio, fim = saida.find("{"), saida.rfind("}")
        if inicio == -1 or fim <= inicio:
            raise ResumoRejeitado(["a resposta não é um JSON"]) from None
        try:
            return json.loads(saida[inicio : fim + 1])
        except json.JSONDecodeError as erro:
            raise ResumoRejeitado([f"JSON malformado ({erro.msg})"]) from erro


def _montar(dados: object) -> Resumo:
    if not isinstance(dados, dict) or set(dados) != {"titulo", "paragrafos", "destaques"}:
        raise ResumoRejeitado(["o JSON deve ter exatamente titulo, paragrafos e destaques"])
    titulo, paragrafos, destaques = dados["titulo"], dados["paragrafos"], dados["destaques"]
    problemas = []
    if not isinstance(titulo, str) or not titulo.strip() or len(titulo) > MAXIMO_DO_TITULO:
        problemas.append("titulo deve ser um texto de até 120 caracteres")
    if not _lista_de_textos(paragrafos, 1, MAXIMO_DE_PARAGRAFOS, MAXIMO_DO_PARAGRAFO):
        problemas.append("paragrafos deve ser uma lista de 1 a 6 textos curtos")
    if not _lista_de_textos(destaques, 0, MAXIMO_DE_DESTAQUES, MAXIMO_DO_DESTAQUE):
        problemas.append("destaques deve ser uma lista de até 6 textos curtos")
    if problemas:
        raise ResumoRejeitado(problemas)
    return Resumo(titulo.strip(), tuple(paragrafos), tuple(destaques))


def _lista_de_textos(valor: object, minimo: int, maximo: int, tamanho: int) -> bool:
    return (
        isinstance(valor, list)
        and minimo <= len(valor) <= maximo
        and all(isinstance(t, str) and t.strip() and len(t) <= tamanho for t in valor)
    )


def _numeros_com_texto(texto: str) -> list[tuple[str, Decimal, int]]:
    return [(bruto, *_interpretar(bruto)) for bruto in _NUMERO.findall(texto)]


def _interpretar(bruto: str) -> tuple[Decimal, int]:
    sinal = -1 if bruto.startswith("-") else 1
    corpo = bruto.lstrip("-")
    if "," in corpo and "." in corpo:
        decimal = "," if corpo.rfind(",") > corpo.rfind(".") else "."
        milhar = "." if decimal == "," else ","
        inteira, _, fracao = corpo.replace(milhar, "").partition(decimal)
    elif "," in corpo:
        if corpo.count(",") > 1:
            inteira, fracao = corpo.replace(",", ""), ""
        else:
            inteira, _, fracao = corpo.partition(",")
    elif "." in corpo:
        if _MILHAR.fullmatch(corpo) and not corpo.startswith("0."):
            inteira, fracao = corpo.replace(".", ""), ""
        else:
            inteira, _, fracao = corpo.partition(".")
    else:
        inteira, fracao = corpo, ""
    return Decimal(f"{inteira}.{fracao}" if fracao else inteira) * sinal, len(fracao)


def _arredondar(valor: Decimal, casas: int) -> Decimal:
    with localcontext() as contexto:
        contexto.prec = 100  # o padrão (28) estouraria com números grandes
        return valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
