"""Casos de uso de consulta: listagem com colunas da definição, filtros e exportação CSV (§2.3).

A listagem e a exportação passam pelo mesmo caminho (`_consultar`), então a mesma versão e os
mesmos filtros valem nas duas.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from forms import repositorio
from forms.banco import Conexao
from forms.exportacao import Coluna, gerar_csv
from forms.formulas import TipoFormula
from forms.models import (
    ErroDeCampo,
    Exibicao,
    Registro,
    RegistroInvalido,
    TipoCampo,
    ValorJson,
    Versao,
)
from forms.repositorio import FiltroDeIgualdade
from forms.servico_base import Cache, tipos_calculados_da_versao

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200

# Mesmos valores que o front manda como texto na URL para um campo sim/não.
_VERDADEIRO = {"true", "sim", "1"}
_FALSO = {"false", "nao", "não", "0"}


@dataclass(frozen=True)
class ListagemDeRegistros:
    versao_id: int
    colunas: tuple[Coluna, ...]
    itens: tuple[Registro, ...]
    total: int
    exibicao: Exibicao
    campo_status: str | None


def listar_registros(
    conexao: Conexao,
    formulario_id: int,
    *,
    versao_id: int | None = None,
    filtros: Mapping[str, str | bool] | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    limite: int = LIMITE_PADRAO,
    deslocamento: int = 0,
    meus: bool = False,
) -> ListagemDeRegistros:
    """Registros de *uma versão* (padrão: a última), com as colunas vindas da definição dela."""
    _conferir_janela(limite, deslocamento)
    versao, colunas, pagina = _consultar(
        conexao,
        formulario_id,
        versao_id,
        filtros or {},
        criado_de,
        criado_ate,
        limite=limite,
        deslocamento=deslocamento,
        meus=meus,
    )
    tipos = tipos_calculados_da_versao(conexao, versao, Cache())
    return ListagemDeRegistros(
        versao.id,
        colunas,
        pagina.itens,
        pagina.total,
        exibicao_efetiva(versao, tipos),
        campo_de_status(versao, tipos),
    )


def exportar_csv(
    conexao: Conexao,
    formulario_id: int,
    *,
    versao_id: int | None = None,
    filtros: Mapping[str, str | bool] | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    meus: bool = False,
) -> bytes:
    """CSV de todos os registros da versão que passam nos filtros (sem paginar)."""
    registros: list[Registro] = []
    deslocamento = 0
    while True:
        _, colunas, pagina = _consultar(
            conexao,
            formulario_id,
            versao_id,
            filtros or {},
            criado_de,
            criado_ate,
            limite=LIMITE_MAXIMO,
            deslocamento=deslocamento,
            meus=meus,
        )
        registros.extend(pagina.itens)
        deslocamento += LIMITE_MAXIMO
        if deslocamento >= pagina.total:
            return gerar_csv(colunas, registros)


def _consultar(
    conexao: Conexao,
    formulario_id: int,
    versao_id: int | None,
    filtros: Mapping[str, str | bool],
    criado_de: date | None,
    criado_ate: date | None,
    *,
    limite: int,
    deslocamento: int,
    meus: bool = False,
) -> tuple[Versao, tuple[Coluna, ...], repositorio.PaginaDeRegistros]:
    versao = (
        repositorio.obter_versao_atual(conexao, formulario_id)
        if versao_id is None
        else repositorio.obter_versao(conexao, versao_id, formulario_id)
    )
    tipos_calculados = tipos_calculados_da_versao(conexao, versao, Cache())
    filtraveis = _filtraveis(versao, tipos_calculados)
    colunas = _colunas(versao, tipos_calculados, set(filtraveis))
    pagina = repositorio.listar_registros(
        conexao,
        versao.id,
        limite=limite,
        deslocamento=deslocamento,
        filtros=_filtros_validados(filtros, filtraveis),
        campos_permitidos=set(filtraveis),
        criado_de=None if criado_de is None else _inicio_do_dia(criado_de),
        criado_ate=None if criado_ate is None else _fim_do_dia(criado_ate),
        criado_por=conexao.usuario_id if meus else None,
    )
    return versao, colunas, pagina


def _colunas(
    versao: Versao, tipos_calculados: Mapping[str, TipoFormula], filtraveis: set[str]
) -> tuple[Coluna, ...]:
    return tuple(
        Coluna(
            id=campo.id,
            rotulo=campo.rotulo,
            unidade=campo.unidade,
            tipo=campo.tipo,
            casas_decimais=campo.casas_decimais,
            tipo_na_formula=tipos_calculados.get(campo.id),
            opcoes=campo.opcoes,
            filtravel=campo.id in filtraveis,
        )
        for campo in versao.definicao.campos
        if campo.tipo is not TipoCampo.SECAO
    )


def _filtraveis(
    versao: Versao, tipos_calculados: Mapping[str, TipoFormula]
) -> dict[str, TipoCampo]:
    """Só igualdade em selecao, sim_nao, texto e calculado booleano. Número e data ficam fora:
    o número é guardado como string, e `"25.5"` e `"25.50"` exigiriam comparação numérica."""
    filtraveis = {}
    for campo in versao.definicao.campos:
        if campo.tipo in (TipoCampo.SELECAO, TipoCampo.SIM_NAO, TipoCampo.TEXTO) or (
            campo.tipo is TipoCampo.CALCULADO
            and tipos_calculados.get(campo.id) is TipoFormula.BOOLEANO
        ):
            filtraveis[campo.id] = campo.tipo
    return filtraveis


def _filtros_validados(
    filtros: Mapping[str, str | bool], filtraveis: Mapping[str, TipoCampo]
) -> list[FiltroDeIgualdade]:
    validados, erros = [], []
    for nome, valor in filtros.items():
        tipo = filtraveis.get(nome)
        if tipo is None:
            erros.append(ErroDeCampo(nome, "Não é possível filtrar por este campo."))
            continue
        booleano = tipo in (TipoCampo.SIM_NAO, TipoCampo.CALCULADO)
        convertido = _como_booleano(valor) if booleano else valor
        if convertido is None or (not booleano and not isinstance(valor, str)):
            erros.append(ErroDeCampo(nome, "Valor de filtro inválido para este campo."))
            continue
        validados.append(FiltroDeIgualdade(nome, convertido, calculado=tipo is TipoCampo.CALCULADO))
    if erros:
        raise RegistroInvalido(tuple(erros))
    return validados


def _como_booleano(valor: str | bool) -> bool | None:
    if isinstance(valor, bool):
        return valor
    texto = valor.strip().casefold()
    if texto in _VERDADEIRO:
        return True
    return False if texto in _FALSO else None


def _conferir_janela(limite: int, deslocamento: int) -> None:
    erros = []
    if not 1 <= limite <= LIMITE_MAXIMO:
        erros.append(ErroDeCampo("limite", f"O limite deve estar entre 1 e {LIMITE_MAXIMO}."))
    if deslocamento < 0:
        erros.append(ErroDeCampo("deslocamento", "O deslocamento não pode ser negativo."))
    if erros:
        raise RegistroInvalido(tuple(erros))


def _inicio_do_dia(dia: date) -> str:
    return datetime.combine(dia, time.min, UTC).isoformat(timespec="seconds")


def _fim_do_dia(dia: date) -> str:
    return datetime.combine(dia, time(23, 59, 59), UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Contagens:
    """Registros por estado do campo de status (§2.3). `campo_status` vazio: a versão não tem
    campo calculado booleano, e tudo conta como "aguardando"."""

    campo_status: str | None
    total: int
    conforme: int
    nao_conforme: int
    erro: int
    aguardando: int


def contar_por_estado(
    conexao: Conexao,
    formulario_id: int,
    *,
    versao_id: int | None = None,
    filtros: Mapping[str, str | bool] | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    meus: bool = False,
) -> Contagens:
    """Contagem por estado com os mesmos filtros da listagem. O estado é decidido aqui, no
    servidor: `true` conforme, `false` não conforme, erro de cálculo, ou ainda sem dados."""
    versao = (
        repositorio.obter_versao_atual(conexao, formulario_id)
        if versao_id is None
        else repositorio.obter_versao(conexao, versao_id, formulario_id)
    )
    tipos_calculados = tipos_calculados_da_versao(conexao, versao, Cache())
    filtraveis = _filtraveis(versao, tipos_calculados)
    campo = campo_de_status(versao, tipos_calculados)
    if campo is None:
        total = repositorio.listar_registros(
            conexao, versao.id, limite=1, deslocamento=0, criado_por=None
        ).total
        return Contagens(None, total, 0, 0, 0, total)
    contagem = repositorio.contar_por_estado(
        conexao,
        versao.id,
        campo,
        filtros=_filtros_validados(filtros or {}, filtraveis),
        campos_permitidos=set(filtraveis),
        criado_de=None if criado_de is None else _inicio_do_dia(criado_de),
        criado_ate=None if criado_ate is None else _fim_do_dia(criado_ate),
        criado_por=conexao.usuario_id if meus else None,
    )
    return Contagens(
        campo,
        sum(contagem.values()),
        contagem["conforme"],
        contagem["nao_conforme"],
        contagem["erro"],
        contagem["aguardando"],
    )


def exibicao_efetiva(versao: Versao, tipos_calculados: Mapping[str, TipoFormula]) -> Exibicao:
    """A `exibicao` da definição, com o que faltar preenchido pelo padrão (§5.2): o primeiro
    calculado numérico em destaque e o primeiro calculado booleano como status."""
    declarada = versao.definicao.exibicao or Exibicao()
    destaque = declarada.destaque
    if destaque is None:
        destaque = next(
            (
                c.id
                for c in versao.definicao.campos
                if c.tipo is TipoCampo.CALCULADO
                and tipos_calculados.get(c.id) is TipoFormula.NUMERO
            ),
            None,
        )
    return Exibicao(destaque, campo_de_status(versao, tipos_calculados), declarada.resumo)


def estado_do_registro(dados: Mapping[str, ValorJson], campo_status: str | None) -> str:
    """`conforme`, `nao_conforme`, `erro`, `aguardando` ou `sem_status`: decidido aqui, nunca
    no front (§7). Calculado guarda `{"valor", "erro"}`."""
    if campo_status is None:
        return "sem_status"
    guardado = dados.get(campo_status)
    if not isinstance(guardado, dict):
        return "aguardando"
    if guardado.get("erro") is not None:
        return "erro"
    valor = guardado.get("valor")
    return "aguardando" if valor is None else ("conforme" if valor else "nao_conforme")


def campo_de_status(versao: Versao, tipos_calculados: Mapping[str, TipoFormula]) -> str | None:
    """O campo de status da `exibicao`, ou o primeiro calculado booleano (§5.2)."""
    exibicao = versao.definicao.exibicao
    if exibicao is not None and exibicao.status is not None:
        return exibicao.status
    for campo in versao.definicao.campos:
        if campo.tipo is TipoCampo.CALCULADO and (
            tipos_calculados.get(campo.id) is TipoFormula.BOOLEANO
        ):
            return campo.id
    return None


__all__: Sequence[str] = [
    "Contagens",
    "ListagemDeRegistros",
    "estado_do_registro",
    "exibicao_efetiva",
    "contar_por_estado",
    "exportar_csv",
    "listar_registros",
]
