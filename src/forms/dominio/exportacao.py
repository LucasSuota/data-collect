"""Formatação das células e geração do CSV para abrir no Excel em português (AGENTS.md §2.3, §12).

Funções puras: recebem as colunas (já derivadas da definição) e os registros e devolvem texto.
UTF-8 com BOM, separador `;`, vírgula decimal.
"""

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from forms.dominio.formulas import TipoFormula
from forms.dominio.models import Registro, TipoCampo, ValorJson

# Início de célula que o Excel e o LibreOffice interpretam como fórmula (§12).
_INICIOS_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class Coluna:
    id: str
    rotulo: str
    unidade: str | None
    tipo: TipoCampo
    casas_decimais: int | None
    # Para `calculado`: o tipo do resultado, que diz como formatar o valor guardado.
    tipo_na_formula: TipoFormula | None = None
    # Para `selecao`: as opções, para o front oferecer o filtro sem reler a definição.
    opcoes: tuple[str, ...] = ()
    # Aceita filtro de igualdade na listagem e no CSV (§2.3): o front só oferece estes.
    filtravel: bool = False

    @property
    def cabecalho(self) -> str:
        return f"{self.rotulo} ({self.unidade})" if self.unidade else self.rotulo


def gerar_csv(colunas: Sequence[Coluna], registros: Sequence[Registro]) -> bytes:
    destino = io.StringIO()
    escritor = csv.writer(destino, delimiter=";", lineterminator="\r\n")
    # O cabeçalho vem do rótulo, texto digitado pelo autor da definição: também é neutralizado.
    escritor.writerow(_neutralizar(coluna.cabecalho) for coluna in colunas)
    for registro in registros:
        escritor.writerow(
            formatar_celula(coluna, registro.dados.get(coluna.id)) for coluna in colunas
        )
    # O BOM faz o Excel reconhecer o UTF-8 (sem ele, os acentos viram lixo).
    return ("﻿" + destino.getvalue()).encode("utf-8")


def formatar_celula(coluna: Coluna, guardado: ValorJson) -> str:
    """Texto da célula a partir do valor guardado no registro. Vazio sai vazio."""
    if coluna.tipo is TipoCampo.CALCULADO:
        return _formatar_calculado(coluna, guardado)
    if guardado is None:
        return ""
    match coluna.tipo:
        case TipoCampo.NUMERO:
            return _numero(str(guardado), coluna.casas_decimais)
        case TipoCampo.SIM_NAO:
            return _sim_nao(guardado)
        case TipoCampo.LOCALIZACAO:
            return _localizacao(guardado)
        case TipoCampo.TEXTO | TipoCampo.SELECAO:
            # Só célula de texto é neutralizada: número (`-3,5`) tem de sair como número.
            return _neutralizar(str(guardado))
        case _:  # data (ISO) e referência (id do registro)
            return str(guardado)


def _formatar_calculado(coluna: Coluna, guardado: ValorJson) -> str:
    if not isinstance(guardado, dict):
        return ""  # registro de uma versão que ainda não tinha esse campo
    if guardado.get("erro") is not None:
        return f"ERRO: {guardado['erro']}"
    valor = guardado.get("valor")
    if valor is None:
        return ""
    if coluna.tipo_na_formula is TipoFormula.NUMERO:
        return _numero(str(valor), coluna.casas_decimais)
    if coluna.tipo_na_formula is TipoFormula.BOOLEANO:
        return _sim_nao(valor)
    return str(valor)


def _numero(valor: str, casas_decimais: int | None) -> str:
    numero = Decimal(valor)
    # `casas_decimais` orienta só a exportação: o valor guardado mantém a precisão total (§7).
    if casas_decimais is not None:
        # Contexto largo: o padrão (28 dígitos) estouraria ao arredondar números grandes.
        with localcontext() as contexto:
            contexto.prec = 100
            numero = numero.quantize(Decimal(1).scaleb(-casas_decimais), rounding=ROUND_HALF_UP)
    texto = format(numero, "f")  # "f" evita a notação científica (`1E+3`)
    if numero == 0:
        texto = texto.lstrip("-")  # -0,04 arredondado a uma casa não é "-0,0"
    return texto.replace(".", ",")


def _sim_nao(valor: ValorJson) -> str:
    return "Sim" if valor is True else "Não"


def _localizacao(valor: ValorJson) -> str:
    if not isinstance(valor, dict):
        return ""
    latitude, longitude = str(valor.get("latitude", "")), str(valor.get("longitude", ""))
    return f"{latitude} / {longitude}".replace(".", ",")


def _neutralizar(texto: str) -> str:
    return "'" + texto if texto.startswith(_INICIOS_PERIGOSOS) else texto
