"""Casos de uso dos registros: criar, atualizar (com cascata), excluir e prévia (§2.3, §2.7).

O servidor valida e recalcula sempre, contra a versão em que o registro nasceu. A mesma função
de cálculo (`formulas.calcular_campos`) serve ao salvar, à cascata e à prévia.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from forms import repositorio, validacao
from forms.banco import Conexao
from forms.formulas import TipoFormula, Valor, ValorDeCampo, calcular_campos
from forms.models import (
    Campo,
    Definicao,
    ErroDeCampo,
    ExclusaoBloqueada,
    NaoEncontrado,
    Registro,
    RegistroInvalido,
    ResultadoCalculado,
    TipoCampo,
    ValorInvalido,
    ValorJson,
    Versao,
)
from forms.repositorio import chave_do_nome
from forms.servico_base import (
    Cache,
    compartilhados_publicados,
    origens_publicadas,
    referencias_brutas,
    tipos_calculados_da_versao,
    transacao,
)
from forms.tipos_campo import ValorNormalizado, normalizar_valor, valor_para_json
from forms.validacao import CampoCompartilhado

_TIPO_NA_FORMULA = {
    TipoCampo.NUMERO: TipoFormula.NUMERO,
    TipoCampo.DATA: TipoFormula.DATA,
    TipoCampo.SIM_NAO: TipoFormula.BOOLEANO,
}


@dataclass(frozen=True)
class ResultadoDaPrevia:
    valida: bool
    erros: tuple[ErroDeCampo, ...]
    calculados: dict[str, ResultadoCalculado]


@dataclass(frozen=True)
class _Preparado:
    dados: dict[str, ValorJson]
    referencias: dict[str, int]


# --- leitura ---


def obter_registro(conexao: Conexao, registro_id: int) -> Registro:
    return repositorio.obter_registro(conexao, registro_id)


# --- criar e atualizar ---


def criar_registro(
    conexao: Conexao,
    formulario_id: int,
    versao_id: int,
    dados: ValorJson,
    agora: datetime,
) -> Registro:
    """Cria o registro numa versão *explícita*: o servidor não valida contra outra em silêncio."""
    versao = repositorio.obter_versao(conexao, versao_id, formulario_id)
    with transacao(conexao):
        preparado = _preparar(conexao, versao, dados, atual=None, cache=Cache())
        registro = repositorio.inserir_registro(
            conexao, formulario_id, versao_id, preparado.dados, agora
        )
        repositorio.substituir_referencias(conexao, registro.id, preparado.referencias)
        return registro


def atualizar_registro(
    conexao: Conexao,
    registro_id: int,
    dados: ValorJson,
    agora: datetime,
) -> Registro:
    """Substitui todos os valores (sem PATCH), recalcula tudo e recalcula os dependentes.

    O registro continua na versão de origem. Tudo, inclusive a cascata, numa transação só.
    """
    atual = repositorio.obter_registro(conexao, registro_id)
    versao = repositorio.obter_versao(conexao, atual.versao_id)
    cache = Cache()
    with transacao(conexao):
        preparado = _preparar(conexao, versao, dados, atual=atual, cache=cache)
        registro = repositorio.atualizar_registro(conexao, registro_id, preparado.dados, agora)
        repositorio.substituir_referencias(conexao, registro_id, preparado.referencias)
        for dependente_id in repositorio.registros_dependentes(conexao, registro_id):
            _recalcular_dependente(conexao, dependente_id, agora, cache)
    return registro


def excluir_registro(conexao: Conexao, registro_id: int) -> None:
    """Apaga de verdade, exceto se outro registro o referencia (§2.7)."""
    repositorio.obter_registro(conexao, registro_id)
    referenciadores = repositorio.registros_que_referenciam(conexao, registro_id)
    if referenciadores:
        lista = ", ".join(str(r) for r in referenciadores)
        raise ExclusaoBloqueada(
            f"O registro {registro_id} é referenciado pelos registros {lista} e não pode ser "
            "excluído."
        )
    with transacao(conexao):
        repositorio.excluir_registro(conexao, registro_id)


def excluir_formulario(conexao: Conexao, formulario_id: int) -> None:
    """Só se nenhum outro formulário depende dele (em qualquer versão) e ele não tem registros."""
    formulario = repositorio.obter_formulario(conexao, formulario_id)
    dependentes = repositorio.formularios_dependentes(conexao, formulario_id, transitivo=False)
    if dependentes:
        nomes = ", ".join(f"'{repositorio.obter_formulario(conexao, i).nome}'" for i in dependentes)
        raise ExclusaoBloqueada(
            f"O formulário '{formulario.nome}' é usado por {nomes} e não pode ser excluído."
        )
    quantidade = repositorio.contar_registros(conexao, formulario_id)
    if quantidade:
        raise ExclusaoBloqueada(
            f"O formulário '{formulario.nome}' tem {quantidade} registro(s) e não pode ser "
            "excluído."
        )
    with transacao(conexao):
        repositorio.excluir_formulario(conexao, formulario_id)


# --- prévia ---


def previa(conexao: Conexao, definicao: ValorJson, valores: ValorJson) -> ResultadoDaPrevia:
    """Calcula os campos sem salvar nada, com a mesma função do salvar.

    Enquanto o usuário digita, o que falta ou está pela metade conta como vazio: a prévia não
    reclama de obrigatório nem de valor inválido (isso é do salvar).
    """
    origens = origens_publicadas(conexao, referencias_brutas(definicao), {})
    analise = validacao.analisar_definicao(definicao, origens)
    if analise.definicao is None:
        return ResultadoDaPrevia(False, analise.erros, {})

    entradas = _entradas_tolerantes(analise.definicao, valores)
    compartilhados = _compartilhados_do_registro(conexao, analise.definicao, entradas, Cache())
    calculados = calcular_campos(analise.definicao.campos, _tipadas(entradas), compartilhados)
    return ResultadoDaPrevia(True, (), calculados)


def _entradas_tolerantes(definicao: Definicao, valores: ValorJson) -> dict[str, ValorNormalizado]:
    informados = valores if isinstance(valores, dict) else {}
    entradas: dict[str, ValorNormalizado] = {}
    for campo in definicao.campos:
        if campo.tipo in (TipoCampo.CALCULADO, TipoCampo.SECAO):
            continue
        try:
            entradas[campo.id] = normalizar_valor(campo, informados.get(campo.id))
        except ValorInvalido:
            entradas[campo.id] = None
    return entradas


# --- o miolo: validar, resolver relações, calcular ---


def _preparar(
    conexao: Conexao,
    versao: Versao,
    dados: ValorJson,
    atual: Registro | None,
    cache: Cache,
) -> _Preparado:
    definicao = versao.definicao
    validado = validacao.validar_registro(definicao, dados)
    erros = list(validado.erros)
    if not erros:
        erros += _erros_de_referencia(conexao, definicao, validado.valores)
    if erros:
        raise RegistroInvalido(tuple(erros))

    compartilhados = _compartilhados_do_registro(conexao, definicao, validado.valores, cache)
    calculados = calcular_campos(definicao.campos, _tipadas(validado.valores), compartilhados)
    return _Preparado(
        dados=_montar_dados(definicao, validado.valores, calculados),
        referencias={
            campo.id: valor
            for campo in definicao.campos
            if campo.tipo is TipoCampo.REFERENCIA
            and isinstance(valor := validado.valores.get(campo.id), int)
        },
    )


def _montar_dados(
    definicao: Definicao,
    valores: dict[str, ValorNormalizado],
    calculados: dict[str, ResultadoCalculado],
) -> dict[str, ValorJson]:
    dados: dict[str, ValorJson] = {}
    for campo in definicao.campos:
        if campo.tipo is TipoCampo.CALCULADO:
            resultado = calculados[campo.id]
            dados[campo.id] = {"valor": resultado.valor, "erro": resultado.erro}
        elif campo.tipo is not TipoCampo.SECAO:
            dados[campo.id] = valor_para_json(valores.get(campo.id))
    return dados


def _tipadas(valores: dict[str, ValorNormalizado]) -> dict[str, Valor]:
    """Só `Decimal`, `date` e `bool` entram em fórmula; texto e localização nunca são usados."""
    return {
        nome: valor for nome, valor in valores.items() if isinstance(valor, Decimal | date | bool)
    }


def _erros_de_referencia(
    conexao: Conexao, definicao: Definicao, valores: dict[str, ValorNormalizado]
) -> list[ErroDeCampo]:
    """A referência exige o id de um registro existente do formulário apontado (qualquer versão)."""
    erros = []
    for campo in definicao.campos:
        destino_id = valores.get(campo.id)
        if campo.tipo is not TipoCampo.REFERENCIA or not isinstance(destino_id, int):
            continue
        if not _e_registro_do_formulario(conexao, destino_id, campo.formulario or ""):
            erros.append(
                ErroDeCampo(
                    campo.id,
                    f"O registro {destino_id} não existe no formulário '{campo.formulario}'.",
                )
            )
    return erros


def _e_registro_do_formulario(conexao: Conexao, registro_id: int, nome: str) -> bool:
    try:
        registro = repositorio.obter_registro(conexao, registro_id)
    except NaoEncontrado:
        return False
    dono = repositorio.obter_formulario(conexao, registro.formulario_id)
    return chave_do_nome(dono.nome) == chave_do_nome(nome)


# --- campos compartilhados da origem ---


def _compartilhados_do_registro(
    conexao: Conexao,
    definicao: Definicao,
    valores: dict[str, ValorNormalizado],
    cache: Cache,
) -> dict[str, ValorDeCampo]:
    """Valores `<referência>__<campo>` vindos dos registros de origem apontados.

    Referência vazia, inexistente ou de outro formulário deixa os compartilhados vazios.
    """
    resultado: dict[str, ValorDeCampo] = {}
    for campo in definicao.campos:
        destino_id = valores.get(campo.id)
        if campo.tipo is not TipoCampo.REFERENCIA or not isinstance(destino_id, int):
            continue
        origem = repositorio.obter_formulario_por_nome(conexao, campo.formulario or "")
        try:
            destino = repositorio.obter_registro(conexao, destino_id)
        except NaoEncontrado:
            continue
        if origem is None or destino.formulario_id != origem.id:
            continue
        esperados = compartilhados_publicados(conexao, origem, cache.compartilhados)
        resultado |= _valores_do_destino(conexao, campo.id, destino, esperados, cache)
    return resultado


def _valores_do_destino(
    conexao: Conexao,
    id_da_referencia: str,
    destino: Registro,
    esperados: dict[str, CampoCompartilhado],
    cache: Cache,
) -> dict[str, ValorDeCampo]:
    versao = repositorio.obter_versao(conexao, destino.versao_id)
    campos = {campo.id: campo for campo in versao.definicao.campos}
    tipos_calculados = tipos_calculados_da_versao(conexao, versao, cache)

    valores = {}
    for id_do_campo, esperado in esperados.items():
        nome = f"{id_da_referencia}__{id_do_campo}"
        campo = campos.get(id_do_campo)
        # Campo que a versão do registro de origem não tem conta como vazio (§2.7).
        if campo is None or esperado.tipo_na_formula is None:
            valores[nome] = ValorDeCampo(None)
        else:
            valores[nome] = _ler_valor_guardado(
                campo, destino.dados.get(id_do_campo), esperado.tipo_na_formula, tipos_calculados
            )
    return valores


def _ler_valor_guardado(
    campo: Campo,
    guardado: ValorJson,
    esperado: TipoFormula,
    tipos_calculados: dict[str, TipoFormula],
) -> ValorDeCampo:
    """Volta o valor guardado em JSON para o tipo que a fórmula do dependente espera."""
    if campo.tipo is TipoCampo.CALCULADO:
        if tipos_calculados.get(campo.id) is not esperado or not isinstance(guardado, dict):
            return ValorDeCampo(None)
        if guardado.get("erro") is not None:
            return ValorDeCampo(None, str(guardado["erro"]))
        return ValorDeCampo(_do_json(guardado.get("valor"), esperado))
    if _TIPO_NA_FORMULA.get(campo.tipo) is not esperado:
        return ValorDeCampo(None)  # a versão antiga tinha outro tipo para esse id
    return ValorDeCampo(_do_json(guardado, esperado))


def _do_json(valor: ValorJson, tipo: TipoFormula) -> Valor:
    if valor is None:
        return None
    if tipo is TipoFormula.NUMERO:
        return Decimal(str(valor))
    if tipo is TipoFormula.DATA:
        return date.fromisoformat(str(valor))
    return bool(valor)


# --- cascata ---


def _recalcular_dependente(
    conexao: Conexao, registro_id: int, agora: datetime, cache: Cache
) -> None:
    """Recalcula só os campos calculados do dependente, contra a versão dele (§2.7).

    Erro de cálculo vira erro no campo; só o que não é cálculo (bug, banco) levanta e desfaz tudo.
    """
    registro = repositorio.obter_registro(conexao, registro_id)
    definicao = repositorio.obter_versao(conexao, registro.versao_id).definicao
    entradas = {
        campo.id: normalizar_valor(campo, registro.dados.get(campo.id))
        for campo in definicao.campos
        if campo.tipo not in (TipoCampo.CALCULADO, TipoCampo.SECAO)
    }
    compartilhados = _compartilhados_do_registro(conexao, definicao, entradas, cache)
    calculados = calcular_campos(definicao.campos, _tipadas(entradas), compartilhados)

    novos = dict(registro.dados)
    for id_do_campo, resultado in calculados.items():
        novos[id_do_campo] = {"valor": resultado.valor, "erro": resultado.erro}
    if novos != registro.dados:  # não regrava (nem muda `atualizado_em`) quem não mudou
        repositorio.atualizar_registro(conexao, registro_id, novos, agora)
