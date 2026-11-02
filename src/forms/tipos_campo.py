"""O que cada tipo de campo aceita, valida e normaliza (AGENTS.md §2.1 e §7).

Aqui o valor entra como veio do JSON e sai tipado (`Decimal`, `date`...) para o cálculo;
`valor_para_json` faz o caminho de volta para o formato guardado e devolvido pela API.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from forms.models import Campo, TipoCampo, ValorInvalido, ValorJson


@dataclass(frozen=True)
class Localizacao:
    latitude: Decimal
    longitude: Decimal


# Foto é a lista de ids dos anexos; referência é o id do registro de origem (§2.7 e §2.8).
type ValorNormalizado = str | bool | int | Decimal | date | Localizacao | tuple[int, ...] | None

_LATITUDE_MAXIMA = Decimal(90)
_LONGITUDE_MAXIMA = Decimal(180)

# Propriedades que todo campo tem; `ESPECIFICACOES` lista só as demais.
PROPRIEDADES_COMUNS = ("id", "tipo", "rotulo")

# `Decimal(str)` aceita "1_000", "NaN", "Infinity" e até dígitos de outros alfabetos ("١٢٣"),
# então a string é conferida por esta regra (só dígitos ASCII) antes de virar `Decimal`.
_NUMERO_EM_TEXTO = re.compile(r"[+-]?[0-9]+(\.[0-9]+)?")
# `date.fromisoformat` aceita também "20261101" e "2026-W44-1"; o contrato é só AAAA-MM-DD.
_DATA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class EspecificacaoDeTipo:
    tipo: TipoCampo
    rotulo: str
    # Propriedades aceitas além de `PROPRIEDADES_COMUNS`; alimenta o `GET /catalogo` (§2.2).
    propriedades: tuple[str, ...]


ESPECIFICACOES: dict[TipoCampo, EspecificacaoDeTipo] = {
    especificacao.tipo: especificacao
    for especificacao in (
        EspecificacaoDeTipo(TipoCampo.TEXTO, "Texto", ("obrigatorio", "compartilhado")),
        EspecificacaoDeTipo(
            TipoCampo.NUMERO,
            "Número",
            ("obrigatorio", "unidade", "casas_decimais", "compartilhado"),
        ),
        EspecificacaoDeTipo(TipoCampo.DATA, "Data", ("obrigatorio", "compartilhado")),
        EspecificacaoDeTipo(
            TipoCampo.SELECAO, "Seleção", ("obrigatorio", "opcoes", "compartilhado")
        ),
        EspecificacaoDeTipo(TipoCampo.SIM_NAO, "Sim/Não", ("obrigatorio", "compartilhado")),
        EspecificacaoDeTipo(
            TipoCampo.CALCULADO,
            "Calculado",
            ("formula", "unidade", "casas_decimais", "compartilhado"),
        ),
        EspecificacaoDeTipo(TipoCampo.SECAO, "Seção", ()),
        EspecificacaoDeTipo(TipoCampo.REFERENCIA, "Referência", ("obrigatorio", "formulario")),
        EspecificacaoDeTipo(TipoCampo.LOCALIZACAO, "Localização", ("obrigatorio", "compartilhado")),
        EspecificacaoDeTipo(TipoCampo.FOTO, "Foto", ("obrigatorio", "maximo", "compartilhado")),
    )
}


def especificacao_do_tipo(nome: str) -> EspecificacaoDeTipo:
    try:
        return ESPECIFICACOES[TipoCampo(nome)]
    except ValueError as erro:
        raise ValorInvalido(f"Tipo de campo desconhecido: '{nome}'.") from erro


def eh_vazio(valor: ValorJson) -> bool:
    """Regra única de "vazio": ausente (lido como `None`), `null` ou string vazia.

    Zero, `False` e espaço não são vazios: são valores. Validação e fórmulas usam esta regra.
    """
    return valor is None or valor == ""


def normalizar_valor(campo: Campo, valor: ValorJson) -> ValorNormalizado:
    """Devolve o valor tipado do campo, ou `None` se vazio; levanta `ValorInvalido`."""
    if eh_vazio(valor):
        return None
    normalizador = _NORMALIZADORES.get(campo.tipo)
    if normalizador is None:
        raise ValorInvalido(f"O campo do tipo '{campo.tipo}' não recebe valor do cliente.")
    return normalizador(campo, valor)


def valor_para_json(valor: ValorNormalizado) -> ValorJson:
    """Formato guardado e devolvido pela API: número e data sempre como string (§7)."""
    if isinstance(valor, Decimal):
        # "f" evita a notação científica ("1E+3") e preserva as casas digitadas ("25.50").
        return format(valor, "f")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Localizacao):
        return {
            "latitude": format(valor.latitude, "f"),
            "longitude": format(valor.longitude, "f"),
        }
    if isinstance(valor, tuple):
        return list(valor)
    return valor


def _normalizar_texto(campo: Campo, valor: ValorJson) -> str:
    if not isinstance(valor, str):
        raise ValorInvalido("O valor deve ser um texto.")
    return valor


def _normalizar_numero(campo: Campo, valor: ValorJson) -> Decimal:
    return _decimal_de(valor)


def _decimal_de(valor: ValorJson) -> Decimal:
    # `bool` é subclasse de `int`: sem esta checagem, `true` viraria o número 1.
    if isinstance(valor, bool) or not isinstance(valor, int | float | str):
        raise ValorInvalido("O valor deve ser um número.")

    if isinstance(valor, str):
        texto = valor.strip()
        if not _NUMERO_EM_TEXTO.fullmatch(texto):
            raise ValorInvalido("O valor deve ser um número, como 25.5 (use ponto decimal).")
        return Decimal(texto)

    if isinstance(valor, int):
        return Decimal(valor)

    # Nunca `Decimal(float)`: carregaria o ruído binário de 0.1. Passa pelo texto do float.
    convertido = Decimal(str(valor))
    if not convertido.is_finite():
        raise ValorInvalido("O valor deve ser um número finito.")
    return convertido


def _normalizar_data(campo: Campo, valor: ValorJson) -> date:
    if not isinstance(valor, str):
        raise ValorInvalido("A data deve ser um texto no formato AAAA-MM-DD.")
    if not _DATA_ISO.fullmatch(valor):
        raise ValorInvalido("A data deve estar no formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(valor)
    except ValueError as erro:
        raise ValorInvalido(f"A data '{valor}' não existe.") from erro


def _normalizar_selecao(campo: Campo, valor: ValorJson) -> str:
    if not isinstance(valor, str) or valor not in campo.opcoes:
        raise ValorInvalido(f"O valor deve ser uma das opções: {', '.join(campo.opcoes)}.")
    return valor


def _normalizar_sim_nao(campo: Campo, valor: ValorJson) -> bool:
    if not isinstance(valor, bool):
        raise ValorInvalido("O valor deve ser sim ou não (verdadeiro ou falso).")
    return valor


def _normalizar_localizacao(campo: Campo, valor: ValorJson) -> Localizacao | None:
    if not isinstance(valor, dict) or not set(valor) <= {"latitude", "longitude"}:
        raise ValorInvalido("A localização deve ser um objeto com latitude e longitude.")

    latitude, longitude = valor.get("latitude"), valor.get("longitude")
    if eh_vazio(latitude) and eh_vazio(longitude):
        return None
    if eh_vazio(latitude) or eh_vazio(longitude):
        raise ValorInvalido("Informe latitude e longitude juntas.")
    return Localizacao(
        latitude=_coordenada(latitude, "latitude", _LATITUDE_MAXIMA),
        longitude=_coordenada(longitude, "longitude", _LONGITUDE_MAXIMA),
    )


def _coordenada(valor: ValorJson, nome: str, limite: Decimal) -> Decimal:
    try:
        coordenada = _decimal_de(valor)
    except ValorInvalido as erro:
        raise ValorInvalido(f"A {nome} deve ser um número.") from erro
    if abs(coordenada) > limite:
        raise ValorInvalido(f"A {nome} deve estar entre -{limite} e {limite}.")
    return coordenada


def _normalizar_foto(campo: Campo, valor: ValorJson) -> tuple[int, ...] | None:
    if not isinstance(valor, list):
        raise ValorInvalido("As fotos devem ser uma lista de ids de anexo.")
    if not valor:
        return None
    if not all(_eh_id(item) for item in valor):
        raise ValorInvalido("Cada foto deve ser o id (inteiro positivo) de um anexo enviado.")
    ids = tuple(item for item in valor if isinstance(item, int))
    if len(set(ids)) != len(ids):
        raise ValorInvalido("A mesma foto não pode aparecer duas vezes.")
    if campo.maximo is not None and len(ids) > campo.maximo:
        raise ValorInvalido(f"Envie no máximo {campo.maximo} fotos.")
    return ids


def _normalizar_referencia(campo: Campo, valor: ValorJson) -> int:
    # Aqui só se confere o formato; a existência do registro é do serviço (§2.7).
    if not _eh_id(valor) or not isinstance(valor, int):
        raise ValorInvalido("O valor de uma referência deve ser o id de um registro.")
    return valor


def _eh_id(valor: ValorJson) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 1


# Calculado e seção nunca recebem valor do cliente: ficam de fora de propósito.
_NORMALIZADORES: dict[TipoCampo, Callable[[Campo, ValorJson], ValorNormalizado]] = {
    TipoCampo.TEXTO: _normalizar_texto,
    TipoCampo.NUMERO: _normalizar_numero,
    TipoCampo.DATA: _normalizar_data,
    TipoCampo.SELECAO: _normalizar_selecao,
    TipoCampo.SIM_NAO: _normalizar_sim_nao,
    TipoCampo.LOCALIZACAO: _normalizar_localizacao,
    TipoCampo.FOTO: _normalizar_foto,
    TipoCampo.REFERENCIA: _normalizar_referencia,
}
