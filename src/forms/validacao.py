"""Validação de uma definição de formulário e de um registro contra ela (AGENTS.md §2.2, §2.3).

Tudo que chega aqui é JSON não confiável. Os dois pontos de entrada devolvem *todos* os erros
de uma vez, localizados pelo `id` do campo (§5.3), porque definição incompleta é o caso normal
enquanto o usuário edita. Sem I/O: o que vem do banco (campos compartilhados) entra por parâmetro.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from forms.formulas import (
    NOMES_RESERVADOS,
    TipoFormula,
    carregar_formula,
    inferir_tipo,
    nomes_usados,
    ordenar_calculados,
)
from forms.models import (
    Campo,
    CicloDeDependencia,
    Definicao,
    DefinicaoInvalida,
    ErroDeCampo,
    FormulaInvalida,
    TipoCampo,
    ValorInvalido,
    ValorJson,
)
from forms.tipos_campo import (
    ESPECIFICACOES,
    PROPRIEDADES_COMUNS,
    ValorNormalizado,
    especificacao_do_tipo,
    normalizar_valor,
)

# Só letras ASCII, dígitos e `_`, sem começar por dígito: o `id` entra numa fórmula como nome,
# e `meu-campo` ou `peso kg` seriam lidos como outra coisa (subtração, erro de sintaxe).
_ID_VALIDO = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Tipos cujo valor entra em fórmula, e o tipo que assumem lá (§7). `calculado` usa o inferido.
_TIPO_NA_FORMULA = {
    TipoCampo.NUMERO: TipoFormula.NUMERO,
    TipoCampo.DATA: TipoFormula.DATA,
    TipoCampo.SIM_NAO: TipoFormula.BOOLEANO,
}


@dataclass(frozen=True)
class CampoCompartilhado:
    """Campo que um formulário de origem libera para os dependentes (§2.7)."""

    tipo: TipoCampo
    # Tipo que o campo tem dentro de uma fórmula; `None` quando o tipo não entra em fórmula.
    tipo_na_formula: TipoFormula | None


# Nome do formulário de origem -> campos que ele compartilha (id -> campo).
type Origens = Mapping[str, Mapping[str, CampoCompartilhado]]


@dataclass(frozen=True)
class AnaliseDeDefinicao:
    erros: tuple[ErroDeCampo, ...]
    # Só existe quando não há erros: nunca se expõe definição parcial.
    definicao: Definicao | None
    # Tipo inferido de cada campo `calculado`, para a validação e o contrato dos compartilhados.
    tipos_calculados: Mapping[str, TipoFormula]


def validar_definicao(dados: ValorJson, origens: Origens | None = None) -> tuple[ErroDeCampo, ...]:
    return analisar_definicao(dados, origens).erros


def exigir_definicao_valida(dados: ValorJson, origens: Origens | None = None) -> Definicao:
    """Para publicar: devolve a definição ou levanta `DefinicaoInvalida` com todos os erros."""
    analise = analisar_definicao(dados, origens)
    if analise.definicao is None:
        raise DefinicaoInvalida(analise.erros)
    return analise.definicao


def analisar_definicao(dados: ValorJson, origens: Origens | None = None) -> AnaliseDeDefinicao:
    erros: list[ErroDeCampo] = []
    brutos = _lista_de_campos(dados, erros)

    campos: list[tuple[str, Campo]] = []  # (prefixo dos erros, campo lido)
    com_erro: set[str] = set()  # ids válidos de campos que não puderam ser lidos
    ids_vistos: set[str] = set()
    for indice, bruto in enumerate(brutos):
        leitura = _ler_campo(indice, bruto, ids_vistos, origens or {})
        erros.extend(leitura.erros)
        if leitura.campo is not None:
            campos.append((leitura.prefixo, leitura.campo))
        elif leitura.id_valido is not None:
            com_erro.add(leitura.id_valido)

    tipos_calculados = _validar_formulas(campos, com_erro, origens or {}, erros)

    definicao = None if erros else Definicao(tuple(campo for _, campo in campos))
    return AnaliseDeDefinicao(tuple(erros), definicao, tipos_calculados)


def compartilhados_da_definicao(
    definicao: Definicao, tipos_calculados: Mapping[str, TipoFormula]
) -> dict[str, CampoCompartilhado]:
    """Campos que a definição libera aos dependentes (§2.7), com o tipo de cada um em fórmula."""
    compartilhados: dict[str, CampoCompartilhado] = {}
    for campo in definicao.campos:
        if not campo.compartilhado:
            continue
        if campo.tipo is TipoCampo.CALCULADO:
            tipo_na_formula = tipos_calculados.get(campo.id)
        else:
            tipo_na_formula = _TIPO_NA_FORMULA.get(campo.tipo)
        compartilhados[campo.id] = CampoCompartilhado(campo.tipo, tipo_na_formula)
    return compartilhados


# --- leitura da estrutura ---


def _lista_de_campos(dados: ValorJson, erros: list[ErroDeCampo]) -> list[ValorJson]:
    if isinstance(dados, dict) and isinstance(dados.get("campos"), list):
        return dados["campos"]
    erros.append(ErroDeCampo("campos", "A definição precisa ter a lista 'campos'."))
    return []


@dataclass
class _Leitura:
    prefixo: str
    erros: list[ErroDeCampo]
    campo: Campo | None = None
    id_valido: str | None = None


def _ler_campo(indice: int, bruto: ValorJson, ids_vistos: set[str], origens: Origens) -> _Leitura:
    leitura = _Leitura(prefixo=f"campos[{indice}]", erros=[])
    if not isinstance(bruto, dict):
        leitura.erros.append(ErroDeCampo(leitura.prefixo, "Cada campo deve ser um objeto."))
        return leitura

    _ler_id(bruto, ids_vistos, leitura)
    leitura_do_tipo = _ler_tipo(bruto, leitura)
    _ler_rotulo(bruto, leitura)
    if leitura_do_tipo is None:
        return leitura

    propriedades = _ler_propriedades(bruto, leitura_do_tipo, leitura, origens)
    if not leitura.erros and isinstance(bruto.get("id"), str):
        leitura.campo = Campo(
            id=bruto["id"], tipo=leitura_do_tipo, rotulo=bruto["rotulo"].strip(), **propriedades
        )
    return leitura


def _ler_id(bruto: dict[str, ValorJson], ids_vistos: set[str], leitura: _Leitura) -> None:
    valor = bruto.get("id")
    indice_do_id = f"{leitura.prefixo}.id"
    if not isinstance(valor, str) or not _ID_VALIDO.fullmatch(valor):
        leitura.erros.append(
            ErroDeCampo(
                indice_do_id,
                "O id é obrigatório e deve ter só letras sem acento, números e '_', "
                "sem começar por número.",
            )
        )
        return
    if valor in NOMES_RESERVADOS:
        leitura.erros.append(ErroDeCampo(indice_do_id, f"O id '{valor}' é reservado."))
    elif "__" in valor:
        leitura.erros.append(
            ErroDeCampo(
                indice_do_id, "O id não pode conter '__' (reservado aos campos compartilhados)."
            )
        )
    elif valor in ids_vistos:
        leitura.erros.append(ErroDeCampo(indice_do_id, f"O id '{valor}' está duplicado."))
    else:
        ids_vistos.add(valor)
        # A partir daqui o id é confiável: os erros deste campo passam a usá-lo, não o índice.
        leitura.prefixo = valor
        leitura.id_valido = valor
        return
    # Id com problema não identifica o campo: continua localizado pelo índice.


def _ler_tipo(bruto: dict[str, ValorJson], leitura: _Leitura) -> TipoCampo | None:
    valor = bruto.get("tipo")
    if not isinstance(valor, str):
        leitura.erros.append(
            ErroDeCampo(f"{leitura.prefixo}.tipo", "O tipo do campo é obrigatório.")
        )
        return None
    try:
        return especificacao_do_tipo(valor).tipo
    except ValorInvalido as erro:
        leitura.erros.append(ErroDeCampo(f"{leitura.prefixo}.tipo", str(erro)))
        return None


def _ler_rotulo(bruto: dict[str, ValorJson], leitura: _Leitura) -> None:
    valor = bruto.get("rotulo")
    if not isinstance(valor, str) or not valor.strip():
        leitura.erros.append(
            ErroDeCampo(
                f"{leitura.prefixo}.rotulo", "O rótulo é obrigatório e não pode ficar vazio."
            )
        )


# --- propriedades de cada tipo ---


def _ler_propriedades(
    bruto: dict[str, ValorJson], tipo: TipoCampo, leitura: _Leitura, origens: Origens
) -> dict[str, object]:
    aceitas = set(PROPRIEDADES_COMUNS) | set(ESPECIFICACOES[tipo].propriedades)
    for nome in bruto:
        if nome not in aceitas:
            leitura.erros.append(
                ErroDeCampo(
                    f"{leitura.prefixo}.{nome}", _mensagem_de_propriedade_proibida(nome, tipo)
                )
            )

    lidas: dict[str, object] = {}
    for nome, leitor in _LEITORES_DE_PROPRIEDADE.items():
        if nome in aceitas and (nome in bruto or nome in _OBRIGATORIAS_POR_TIPO.get(tipo, ())):
            problema = leitor(bruto.get(nome), origens)
            if isinstance(problema, str):
                leitura.erros.append(ErroDeCampo(f"{leitura.prefixo}.{nome}", problema))
            else:
                lidas[nome] = problema.valor
    return lidas


def _mensagem_de_propriedade_proibida(nome: str, tipo: TipoCampo) -> str:
    if nome == "compartilhado":
        return f"Campos do tipo {ESPECIFICACOES[tipo].rotulo.lower()} não podem ser compartilhados."
    return f"A propriedade '{nome}' não existe no tipo {tipo.value}."


@dataclass(frozen=True)
class _Lido:
    valor: object


# Cada leitor devolve o valor aceito (`_Lido`) ou a mensagem de erro.
def _booleano(valor: ValorJson, origens: Origens) -> _Lido | str:
    return _Lido(valor) if isinstance(valor, bool) else "Deve ser verdadeiro ou falso."


def _texto(valor: ValorJson, origens: Origens) -> _Lido | str:
    return _Lido(valor) if isinstance(valor, str) else "Deve ser um texto."


def _inteiro_a_partir_de(minimo: int, mensagem: str):
    def ler(valor: ValorJson, origens: Origens) -> _Lido | str:
        # `bool` é subclasse de `int`: `true` não é um inteiro válido aqui.
        if type(valor) is int and valor >= minimo:
            return _Lido(valor)
        return mensagem

    return ler


def _opcoes(valor: ValorJson, origens: Origens) -> _Lido | str:
    if not isinstance(valor, list) or not valor:
        return "As opções devem ser uma lista não vazia de textos."
    if not all(isinstance(opcao, str) and opcao.strip() for opcao in valor):
        return "Cada opção deve ser um texto não vazio."
    if len(set(valor)) != len(valor):
        return "As opções não podem se repetir."
    return _Lido(tuple(valor))


def _formulario(valor: ValorJson, origens: Origens) -> _Lido | str:
    if not isinstance(valor, str) or not valor.strip():
        return "A referência precisa do nome do formulário de origem."
    if valor not in origens:
        return f"O formulário '{valor}' não existe."
    return _Lido(valor)


def _formula(valor: ValorJson, origens: Origens) -> _Lido | str:
    return _Lido(valor) if isinstance(valor, str) else "A fórmula deve ser um texto."


_LEITORES_DE_PROPRIEDADE = {
    "obrigatorio": _booleano,
    "compartilhado": _booleano,
    "unidade": _texto,
    "casas_decimais": _inteiro_a_partir_de(
        0, "As casas decimais devem ser um inteiro a partir de 0."
    ),
    "maximo": _inteiro_a_partir_de(1, "O máximo de fotos deve ser um inteiro a partir de 1."),
    "opcoes": _opcoes,
    "formulario": _formulario,
    "formula": _formula,
}

_OBRIGATORIAS_POR_TIPO = {
    TipoCampo.SELECAO: ("opcoes",),
    TipoCampo.REFERENCIA: ("formulario",),
    TipoCampo.CALCULADO: ("formula",),
}


# --- fórmulas ---


def _validar_formulas(
    campos: list[tuple[str, Campo]],
    com_erro: set[str],
    origens: Origens,
    erros: list[ErroDeCampo],
) -> dict[str, TipoFormula]:
    calculados = {campo.id: campo for _, campo in campos if campo.tipo is TipoCampo.CALCULADO}
    tipos, nao_utilizaveis = _tipos_dos_nomes(campos, com_erro, origens)

    formulas = {}
    falhas: set[str] = set()
    for id_do_campo, campo in calculados.items():
        try:
            formulas[id_do_campo] = carregar_formula(campo.formula or "")
        except FormulaInvalida as erro:
            erros.append(_erro_de_formula(id_do_campo, erro))
            falhas.add(id_do_campo)

    nomes = {id_do_campo: nomes_usados(formula) for id_do_campo, formula in formulas.items()}
    try:
        ordem = ordenar_calculados(nomes)
    except CicloDeDependencia as ciclo:
        erros.extend(ciclo.erros)
        return {}

    tipos_calculados: dict[str, TipoFormula] = {}
    for id_do_campo in ordem:
        if any(
            nome in falhas or _usa_referencia_com_erro(nome, com_erro)
            for nome in nomes[id_do_campo]
        ):
            falhas.add(id_do_campo)  # a causa já foi apontada na origem: sem erro em cascata
            continue
        if _faltam_compartilhados(
            id_do_campo, nomes[id_do_campo], campos, tipos, nao_utilizaveis, origens, erros
        ):
            falhas.add(id_do_campo)
            continue
        try:
            tipo = inferir_tipo(formulas[id_do_campo], tipos | tipos_calculados, nao_utilizaveis)
        except FormulaInvalida as erro:
            erros.append(_erro_de_formula(id_do_campo, erro))
            falhas.add(id_do_campo)
            continue
        tipos_calculados[id_do_campo] = tipo
        _conferir_casas_decimais(calculados[id_do_campo], tipo, erros)
    return tipos_calculados


def _usa_referencia_com_erro(nome: str, com_erro: set[str]) -> bool:
    """`ensaio__umidade` quando o campo `ensaio` não pôde ser lido (origem inexistente, por
    exemplo): o erro já está em `ensaio.formulario`, e repeti-lo na fórmula só atrapalha."""
    id_da_referencia, separador, _ = nome.partition("__")
    return bool(separador) and id_da_referencia in com_erro


def _tipos_dos_nomes(
    campos: list[tuple[str, Campo]], com_erro: set[str], origens: Origens
) -> tuple[dict[str, TipoFormula], dict[str, str]]:
    tipos: dict[str, TipoFormula] = {}
    nao_utilizaveis: dict[str, str] = {id_com_erro: "com erro" for id_com_erro in com_erro}
    for _, campo in campos:
        if campo.tipo in _TIPO_NA_FORMULA:
            tipos[campo.id] = _TIPO_NA_FORMULA[campo.tipo]
        elif campo.tipo is not TipoCampo.CALCULADO:
            nao_utilizaveis[campo.id] = campo.tipo.value
        if campo.tipo is TipoCampo.REFERENCIA and campo.formulario in origens:
            for id_compartilhado, compartilhado in origens[campo.formulario].items():
                nome = f"{campo.id}__{id_compartilhado}"
                if compartilhado.tipo_na_formula is not None:
                    tipos[nome] = compartilhado.tipo_na_formula
                else:
                    nao_utilizaveis[nome] = compartilhado.tipo.value
    return tipos, nao_utilizaveis


def _faltam_compartilhados(
    id_do_campo: str,
    nomes: tuple[str, ...],
    campos: list[tuple[str, Campo]],
    tipos: Mapping[str, TipoFormula],
    nao_utilizaveis: Mapping[str, str],
    origens: Origens,
    erros: list[ErroDeCampo],
) -> bool:
    """Aponta `ref__campo` que a origem não compartilha, com mensagem melhor que 'não existe'."""
    referencias = {c.id: c for _, c in campos if c.tipo is TipoCampo.REFERENCIA}
    achou = False
    for nome in nomes:
        id_da_referencia, separador, id_compartilhado = nome.partition("__")
        referencia = referencias.get(id_da_referencia)
        if not separador or referencia is None or referencia.formulario not in origens:
            continue
        if nome not in tipos and nome not in nao_utilizaveis:
            erros.append(
                ErroDeCampo(
                    f"{id_do_campo}.formula",
                    f"O formulário '{referencia.formulario}' não compartilha o campo "
                    f"'{id_compartilhado}'.",
                )
            )
            achou = True
    return achou


def _erro_de_formula(id_do_campo: str, erro: FormulaInvalida) -> ErroDeCampo:
    return ErroDeCampo(f"{id_do_campo}.formula", str(erro), erro.posicao)


def _conferir_casas_decimais(campo: Campo, tipo: TipoFormula, erros: list[ErroDeCampo]) -> None:
    if campo.casas_decimais is not None and tipo is not TipoFormula.NUMERO:
        erros.append(
            ErroDeCampo(
                f"{campo.id}.casas_decimais",
                "As casas decimais só valem para calculado numérico, mas esta fórmula "
                f"resulta em {tipo.value}.",
            )
        )


# --- registro ---


@dataclass(frozen=True)
class ValidacaoDeRegistro:
    erros: tuple[ErroDeCampo, ...]
    # Valores normalizados dos campos de entrada (`Decimal`, `date`...), `None` quando vazios.
    # Prontos para o cálculo; só são confiáveis quando `erros` está vazio.
    valores: Mapping[str, ValorNormalizado]


def validar_registro(definicao: Definicao, dados: ValorJson) -> ValidacaoDeRegistro:
    """Confere o registro contra a definição; devolve todos os erros por `id`.

    Erro de *cálculo* nunca passa por aqui: ele é tratado em `calcular_campos` (§7).
    """
    if not isinstance(dados, dict):
        return ValidacaoDeRegistro((ErroDeCampo("dados", "Os dados devem ser um objeto."),), {})

    erros: list[ErroDeCampo] = []
    por_id = {campo.id: campo for campo in definicao.campos}

    for chave in dados:
        problema = _problema_da_chave(por_id.get(chave))
        if problema is not None:
            erros.append(ErroDeCampo(chave, problema))

    valores: dict[str, ValorNormalizado] = {}
    for campo in definicao.campos:
        if campo.tipo in (TipoCampo.CALCULADO, TipoCampo.SECAO):
            continue
        valor = dados.get(campo.id)
        try:
            normalizado = normalizar_valor(campo, valor)
        except ValorInvalido as erro:
            erros.append(ErroDeCampo(campo.id, str(erro)))
            continue
        if normalizado is None and campo.obrigatorio:
            erros.append(ErroDeCampo(campo.id, "Campo obrigatório."))
        valores[campo.id] = normalizado
    return ValidacaoDeRegistro(tuple(erros), valores)


def _problema_da_chave(campo: Campo | None) -> str | None:
    if campo is None:
        return "Este campo não existe na definição."
    if campo.tipo is TipoCampo.CALCULADO:
        return "Campo calculado não pode ser enviado: o servidor o calcula."
    if campo.tipo is TipoCampo.SECAO:
        return "Seção é só visual e não recebe valor."
    return None
