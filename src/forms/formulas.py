"""Fórmulas: análise, tipos, ordem de cálculo e avaliação (AGENTS.md §7).

O texto da fórmula nunca é executado: vira árvore com `ast.parse`, cada nó precisa estar numa
lista de permissão, e um avaliador próprio percorre a árvore. Nada aqui usa `eval`, `exec` nem
`compile`. A aritmética é sempre `Decimal`, nunca `float`.
"""

import ast
import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import (
    Context,
    Decimal,
    DivisionByZero,
    DivisionUndefined,
    InvalidOperation,
    Overflow,
    localcontext,
)
from enum import StrEnum
from functools import partial

from forms.models import (
    Campo,
    CicloDeDependencia,
    ErroDeCalculo,
    FormulaInvalida,
    Posicao,
    ResultadoCalculado,
    TipoCampo,
)

# --- tipos, valores e a tabela única de funções ---


class TipoFormula(StrEnum):
    NUMERO = "numero"
    DATA = "data"
    BOOLEANO = "booleano"
    # Só existe como resultado de `dias(n)`; não pode ser o resultado final de um campo.
    DURACAO = "duracao"


_ROTULOS_DOS_TIPOS = {
    TipoFormula.NUMERO: "número",
    TipoFormula.DATA: "data",
    TipoFormula.BOOLEANO: "sim/não",
    TipoFormula.DURACAO: "duração",
}

# Valor de uma expressão em tempo de execução; `None` é "vazio" e propaga (§7).
type Valor = Decimal | date | timedelta | bool | None
# Argumento ainda não avaliado: `se` precisa avaliar só o ramo escolhido.
type Argumento = Callable[[], Valor]

# Precisão fixa (a padrão do Python) para o resultado não depender de configuração global.
# Divisão por zero, operação inválida e estouro viram exceção em vez de NaN/Infinity.
CONTEXTO_DECIMAL = Context(prec=28, traps=[InvalidOperation, DivisionByZero, Overflow])
# 28 dígitos significativos, a mesma precisão do contexto: a conta não perde nem inventa dígitos.
PI = Decimal("3.141592653589793238462643383")

# Retorna o tipo do resultado ou, se os tipos dos argumentos não servem, a mensagem de erro.
type InferirTipo = Callable[[Sequence[TipoFormula]], TipoFormula | str]
type Calcular = Callable[[Sequence[Argumento]], Valor]


@dataclass(frozen=True)
class FuncaoDeFormula:
    nome: str
    assinatura: str
    descricao: str
    exemplo: str
    minimo_de_argumentos: int
    maximo_de_argumentos: int | None
    inferir_tipo: InferirTipo
    calcular: Calcular


@dataclass(frozen=True)
class ConstanteDeFormula:
    nome: str
    valor: Decimal
    tipo: TipoFormula
    descricao: str


def _rotulos(tipos: Sequence[TipoFormula]) -> str:
    return ", ".join(_ROTULOS_DOS_TIPOS[tipo] for tipo in tipos)


def _avaliar_todos(argumentos: Sequence[Argumento]) -> list[Valor] | None:
    """Avalia todos os argumentos; qualquer vazio torna o resultado vazio (nada é ignorado)."""
    valores = [argumento() for argumento in argumentos]
    return None if any(valor is None for valor in valores) else valores


def _so_numeros(nome: str) -> InferirTipo:
    def inferir(tipos: Sequence[TipoFormula]) -> TipoFormula | str:
        if any(tipo is not TipoFormula.NUMERO for tipo in tipos):
            return f"{nome}() só aceita números, mas recebeu: {_rotulos(tipos)}."
        return TipoFormula.NUMERO

    return inferir


def _inferir_se(tipos: Sequence[TipoFormula]) -> TipoFormula | str:
    condicao, se_verdadeiro, se_falso = tipos
    if condicao is not TipoFormula.BOOLEANO:
        return (
            "A condição de se() deve ser uma comparação ou um valor de sim/não, "
            f"mas é {_ROTULOS_DOS_TIPOS[condicao]}."
        )
    if se_verdadeiro is not se_falso:
        return (
            "Os dois resultados de se() devem ter o mesmo tipo, mas são "
            f"{_ROTULOS_DOS_TIPOS[se_verdadeiro]} e {_ROTULOS_DOS_TIPOS[se_falso]}."
        )
    return se_verdadeiro


def _inferir_dias(tipos: Sequence[TipoFormula]) -> TipoFormula | str:
    if tipos[0] is not TipoFormula.NUMERO:
        return f"dias() recebe um número de dias, mas recebeu {_ROTULOS_DOS_TIPOS[tipos[0]]}."
    return TipoFormula.DURACAO


def _calcular_soma(argumentos: Sequence[Argumento]) -> Valor:
    valores = _avaliar_todos(argumentos)
    return None if valores is None else sum(valores, Decimal(0))


def _calcular_media(argumentos: Sequence[Argumento]) -> Valor:
    valores = _avaliar_todos(argumentos)
    return None if valores is None else sum(valores, Decimal(0)) / Decimal(len(valores))


def _calcular_min(argumentos: Sequence[Argumento]) -> Valor:
    valores = _avaliar_todos(argumentos)
    return None if valores is None else min(valores)


def _calcular_max(argumentos: Sequence[Argumento]) -> Valor:
    valores = _avaliar_todos(argumentos)
    return None if valores is None else max(valores)


def _calcular_se(argumentos: Sequence[Argumento]) -> Valor:
    condicao = argumentos[0]()
    if condicao is None:
        return None
    # Só o ramo escolhido é avaliado: `se(d == 0, 0, x / d)` não erra por divisão por zero.
    return argumentos[1]() if condicao else argumentos[2]()


def _calcular_dias(argumentos: Sequence[Argumento]) -> Valor:
    valores = _avaliar_todos(argumentos)
    if valores is None:
        return None
    quantidade = valores[0]
    if quantidade != quantidade.to_integral_value():
        raise ErroDeCalculo(f"dias() exige um número inteiro de dias, mas recebeu {quantidade}.")
    return timedelta(days=int(quantidade))


# A única fonte das funções: o parser, a inferência de tipos, o avaliador e o catálogo
# (`GET /catalogo`) leem esta tabela, para nenhuma lista paralela dessincronizar.
FUNCOES: dict[str, FuncaoDeFormula] = {
    funcao.nome: funcao
    for funcao in (
        FuncaoDeFormula(
            nome="soma",
            assinatura="soma(a, b, ...)",
            descricao="Soma de um ou mais números.",
            exemplo="soma(carga_1, carga_2, carga_3)",
            minimo_de_argumentos=1,
            maximo_de_argumentos=None,
            inferir_tipo=_so_numeros("soma"),
            calcular=_calcular_soma,
        ),
        FuncaoDeFormula(
            nome="media",
            assinatura="media(a, b, ...)",
            descricao="Média aritmética de um ou mais números.",
            exemplo="media(carga_1, carga_2)",
            minimo_de_argumentos=1,
            maximo_de_argumentos=None,
            inferir_tipo=_so_numeros("media"),
            calcular=_calcular_media,
        ),
        FuncaoDeFormula(
            nome="min",
            assinatura="min(a, b, ...)",
            descricao="Menor de um ou mais números.",
            exemplo="min(carga_1, carga_2)",
            minimo_de_argumentos=1,
            maximo_de_argumentos=None,
            inferir_tipo=_so_numeros("min"),
            calcular=_calcular_min,
        ),
        FuncaoDeFormula(
            nome="max",
            assinatura="max(a, b, ...)",
            descricao="Maior de um ou mais números.",
            exemplo="max(carga_1, carga_2)",
            minimo_de_argumentos=1,
            maximo_de_argumentos=None,
            inferir_tipo=_so_numeros("max"),
            calcular=_calcular_max,
        ),
        FuncaoDeFormula(
            nome="se",
            assinatura="se(condicao, se_verdadeiro, se_falso)",
            descricao=(
                "Escolhe entre dois valores do mesmo tipo conforme a condição. "
                "Só o resultado escolhido é calculado."
            ),
            exemplo="se(diametro == 0, 0, carga / diametro)",
            minimo_de_argumentos=3,
            maximo_de_argumentos=3,
            inferir_tipo=_inferir_se,
            calcular=_calcular_se,
        ),
        FuncaoDeFormula(
            nome="dias",
            assinatura="dias(n)",
            descricao="Duração de n dias inteiros; só serve para somar ou subtrair de uma data.",
            exemplo="dias(28)",
            minimo_de_argumentos=1,
            maximo_de_argumentos=1,
            inferir_tipo=_inferir_dias,
            calcular=_calcular_dias,
        ),
    )
}

CONSTANTES: dict[str, ConstanteDeFormula] = {
    "pi": ConstanteDeFormula(
        nome="pi",
        valor=PI,
        tipo=TipoFormula.NUMERO,
        descricao="Razão entre a circunferência e o diâmetro, com 28 dígitos significativos.",
    )
}

# Nomes que nenhum campo pode ter como `id` (§7).
NOMES_RESERVADOS = frozenset(FUNCOES) | frozenset(CONSTANTES)

# --- análise: do texto à árvore verificada ---

# Limite de aninhamento: garante que a inferência e a avaliação (recursivas) nunca estourem a
# pilha. Fórmula real tem poucos níveis; uma soma de muitos termos deve usar soma(...).
PROFUNDIDADE_MAXIMA = 150

# Só estes nós de expressão entram. Os operadores e o contexto (`Load`) são conferidos no
# nó pai, porque os nós de operador não têm posição no texto.
_EXPRESSOES_PERMITIDAS = (
    ast.Constant,
    ast.Name,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Call,
)
_OPERADORES_BINARIOS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_OPERADORES_UNARIOS = (ast.USub, ast.Not)
_OPERADORES_DE_COMPARACAO = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)

# `bool` é subclasse de `int`, então a checagem de constante usa o tipo exato.
_TIPOS_DE_CONSTANTE = (int, float, bool)

_MENSAGEM_DE_OPERADOR = (
    "Esse operador não é permitido na fórmula; use + - * / **, comparações, and, or e not."
)

_MENSAGENS_POR_NO: dict[type[ast.AST], str] = {
    ast.Attribute: "Acesso a atributo não é permitido na fórmula.",
    ast.Subscript: "Acesso por índice ou fatia não é permitido na fórmula.",
    ast.Lambda: "Funções anônimas (lambda) não são permitidas na fórmula.",
    ast.JoinedStr: "f-strings não são permitidas na fórmula.",
    ast.ListComp: "A fórmula não aceita compreensão de lista, conjunto, dicionário ou gerador.",
    ast.SetComp: "A fórmula não aceita compreensão de lista, conjunto, dicionário ou gerador.",
    ast.DictComp: "A fórmula não aceita compreensão de lista, conjunto, dicionário ou gerador.",
    ast.GeneratorExp: "A fórmula não aceita compreensão de lista, conjunto, dicionário ou gerador.",
    ast.IfExp: "Use a função se(condição, a, b) no lugar de 'a if condição else b'.",
    ast.NamedExpr: "A fórmula não aceita atribuição.",
}


@dataclass(frozen=True)
class Formula:
    """Texto + árvore já verificada; o texto serve às mensagens com `posicao` e às constantes."""

    texto: str
    arvore: ast.Expression


def carregar_formula(texto: str) -> Formula:
    return Formula(texto, analisar_formula(texto))


def analisar_formula(texto: str) -> ast.Expression:
    """Devolve a árvore da fórmula já verificada, ou levanta `FormulaInvalida`."""
    if not texto.strip():
        raise FormulaInvalida("A fórmula está vazia.", Posicao(0, len(texto)))

    try:
        arvore = ast.parse(texto, mode="eval")
    except SyntaxError as erro:
        raise FormulaInvalida(
            "Sintaxe inválida na fórmula.", _posicao_do_erro_de_sintaxe(texto, erro)
        ) from erro
    except (ValueError, RecursionError, MemoryError) as erro:
        # Byte nulo (ValueError) e aninhamento absurdo (RecursionError/MemoryError)
        # são entrada do usuário, não bug: viram erro de fórmula, não exceção crua.
        raise FormulaInvalida(
            "A fórmula contém caracteres inválidos ou é complexa demais para ser analisada.",
            Posicao(0, len(texto)),
        ) from erro

    if _profundidade(arvore) > PROFUNDIDADE_MAXIMA:
        raise FormulaInvalida(
            "A fórmula tem expressões aninhadas demais. Simplifique, ou use soma(...) "
            "no lugar de muitas somas encadeadas.",
            Posicao(0, len(texto)),
        )

    problema = _procurar_problema(arvore)
    if problema is not None:
        no, mensagem = problema
        raise FormulaInvalida(mensagem, _posicao_do_no(texto, no))
    return arvore


def _profundidade(arvore: ast.Expression) -> int:
    # Iterativo de propósito: é justamente a árvore funda que não pode estourar a pilha.
    maxima = 0
    pilha = [(arvore.body, 1)]
    while pilha:
        no, nivel = pilha.pop()
        maxima = max(maxima, nivel)
        pilha.extend((filho, nivel + 1) for filho in ast.iter_child_nodes(no))
    return maxima


def _procurar_problema(arvore: ast.Expression) -> tuple[ast.expr, str] | None:
    # `ast.walk` é iterativo, então uma árvore funda não estoura a pilha aqui.
    for no in ast.walk(arvore.body):
        # Operadores e contexto não têm posição; o nó pai que os contém já foi conferido.
        if not isinstance(no, ast.expr):
            continue
        problema = _problema_do_no(no)
        if problema is not None:
            return problema
    return None


def _problema_do_no(no: ast.expr) -> tuple[ast.expr, str] | None:
    if not isinstance(no, _EXPRESSOES_PERMITIDAS):
        mensagem = _MENSAGENS_POR_NO.get(
            type(no), f"Essa construção não é permitida na fórmula ({type(no).__name__})."
        )
        return no, mensagem

    if isinstance(no, ast.Constant) and type(no.value) not in _TIPOS_DE_CONSTANTE:
        if isinstance(no.value, str):
            return no, "Constantes de texto não são permitidas na fórmula."
        return no, "Essa constante não é permitida na fórmula; use números ou verdadeiro/falso."

    if isinstance(no, ast.BinOp) and not isinstance(no.op, _OPERADORES_BINARIOS):
        return no, _MENSAGEM_DE_OPERADOR
    if isinstance(no, ast.UnaryOp) and not isinstance(no.op, _OPERADORES_UNARIOS):
        return no, _MENSAGEM_DE_OPERADOR
    if isinstance(no, ast.Compare):
        if len(no.ops) > 1:
            return (
                no,
                "Comparações encadeadas não são permitidas; use 'and' entre duas comparações.",
            )
        if not isinstance(no.ops[0], _OPERADORES_DE_COMPARACAO):
            return no, _MENSAGEM_DE_OPERADOR

    if isinstance(no, ast.Call):
        return _problema_da_chamada(no)
    return None


def _problema_da_chamada(chamada: ast.Call) -> tuple[ast.expr, str] | None:
    if not isinstance(chamada.func, ast.Name):
        # Se o que está sendo chamado já é uma construção proibida (lambda, atributo...),
        # a mensagem dela é mais útil do que um aviso genérico sobre chamadas.
        return _problema_do_no(chamada.func) or (
            chamada.func,
            "Só é permitido chamar funções pelo nome.",
        )
    nome = chamada.func.id
    if nome in CONSTANTES:
        return chamada, f"'{nome}' é uma constante: use {nome} sem parênteses."
    funcao = FUNCOES.get(nome)
    if funcao is None:
        return chamada, f"Função '{nome}' não permitida na fórmula."
    if chamada.keywords or any(isinstance(argumento, ast.Starred) for argumento in chamada.args):
        return chamada, "Não são permitidos argumentos nomeados nem com * nas chamadas."
    if not _aridade_valida(funcao, len(chamada.args)):
        return chamada, _mensagem_de_aridade(funcao)
    return None


def _aridade_valida(funcao: FuncaoDeFormula, quantidade: int) -> bool:
    maximo = funcao.maximo_de_argumentos
    return quantidade >= funcao.minimo_de_argumentos and (maximo is None or quantidade <= maximo)


def _mensagem_de_aridade(funcao: FuncaoDeFormula) -> str:
    minimo, maximo = funcao.minimo_de_argumentos, funcao.maximo_de_argumentos
    plural = "argumento" if minimo == 1 else "argumentos"
    if maximo is None:
        exigencia = f"pelo menos {minimo} {plural}"
    else:
        exigencia = f"exatamente {minimo} {plural}"
    return f"{funcao.nome}() precisa de {exigencia}. Uso: {funcao.assinatura}."


def _inicio_da_linha(texto: str, linha: int) -> int:
    """Deslocamento, em caracteres, do começo da linha (1-based) dentro do texto."""
    return sum(len(anterior) + 1 for anterior in texto.split("\n")[: linha - 1])


def _posicao_do_no(texto: str, no: ast.expr) -> Posicao:
    # O `ast` mede a coluna em bytes UTF-8, mas o front sublinha por caracteres.
    # Sem a conversão, um "ç" antes do trecho deslocaria o sublinhado em um caractere.
    def deslocamento(linha: int, coluna_em_bytes: int) -> int:
        texto_da_linha = texto.split("\n")[linha - 1]
        coluna = len(texto_da_linha.encode()[:coluna_em_bytes].decode(errors="ignore"))
        return _inicio_da_linha(texto, linha) + coluna

    # `end_lineno` e `end_col_offset` são opcionais no tipo, mas o parser sempre os preenche.
    linha_final = no.end_lineno or no.lineno
    coluna_final = no.col_offset if no.end_col_offset is None else no.end_col_offset
    return Posicao(
        inicio=deslocamento(no.lineno, no.col_offset),
        fim=deslocamento(linha_final, coluna_final),
    )


def _posicao_do_erro_de_sintaxe(texto: str, erro: SyntaxError) -> Posicao:
    tudo = Posicao(0, len(texto))
    if not erro.lineno or not erro.offset or erro.offset < 1:
        return tudo

    # O `offset` do SyntaxError é 1-based e, desde o Python 3.10, em caracteres.
    inicio = _inicio_da_linha(texto, erro.lineno) + erro.offset - 1
    if erro.end_lineno and erro.end_offset and erro.end_offset >= 1:
        fim = _inicio_da_linha(texto, erro.end_lineno) + erro.end_offset - 1
    else:
        fim = inicio + 1
    inicio = min(inicio, len(texto))
    return Posicao(inicio=inicio, fim=min(max(fim, inicio), len(texto)))


# --- inferência de tipos (ao publicar) ---

_SIMBOLOS_DE_OPERADOR: dict[type[ast.AST], str] = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.Pow: "**",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
}


def inferir_tipo(
    formula: Formula,
    tipos_dos_nomes: Mapping[str, TipoFormula],
    nao_utilizaveis: Mapping[str, str] | None = None,
) -> TipoFormula:
    """Tipo do resultado da fórmula, sem executá-la; levanta `FormulaInvalida` com `posicao`.

    `tipos_dos_nomes` traz o tipo de cada campo usável (inclusive `calculado`, já inferido
    na ordem das dependências, e os compartilhados como `ref__campo`). `nao_utilizaveis` mapeia
    o nome dos campos de tipo texto, seleção etc. para o tipo, só para a mensagem de erro.
    Recebe tudo por parâmetro para continuar pura, sem consultar banco.
    """
    inferidor = _Inferidor(formula.texto, tipos_dos_nomes, nao_utilizaveis or {})
    corpo = formula.arvore.body
    tipo = inferidor.tipo_de(corpo)
    if tipo is TipoFormula.DURACAO:
        raise inferidor.erro(
            corpo, "O resultado não pode ser uma duração: some-a ou subtraia-a de uma data."
        )
    return tipo


class _Inferidor:
    def __init__(
        self, texto: str, tipos: Mapping[str, TipoFormula], nao_utilizaveis: Mapping[str, str]
    ) -> None:
        self._texto = texto
        self._tipos = tipos
        self._nao_utilizaveis = nao_utilizaveis

    def erro(self, no: ast.expr, mensagem: str) -> FormulaInvalida:
        return FormulaInvalida(mensagem, _posicao_do_no(self._texto, no))

    def tipo_de(self, no: ast.expr) -> TipoFormula:
        if isinstance(no, ast.Constant):
            return TipoFormula.BOOLEANO if isinstance(no.value, bool) else TipoFormula.NUMERO
        if isinstance(no, ast.Name):
            return self._tipo_do_nome(no)
        if isinstance(no, ast.BinOp):
            return self._tipo_binario(no)
        if isinstance(no, ast.UnaryOp):
            return self._tipo_unario(no)
        if isinstance(no, ast.BoolOp):
            return self._tipo_booleano(no)
        if isinstance(no, ast.Compare):
            return self._tipo_de_comparacao(no)
        if isinstance(no, ast.Call):
            return self._tipo_da_chamada(no)
        # O parser já barrou qualquer outro nó; chegar aqui é bug, não entrada do usuário.
        raise self.erro(no, f"Construção não prevista na fórmula ({type(no).__name__}).")

    def _tipo_do_nome(self, no: ast.Name) -> TipoFormula:
        if no.id in CONSTANTES:
            return CONSTANTES[no.id].tipo
        if no.id in self._tipos:
            return self._tipos[no.id]
        if no.id in self._nao_utilizaveis:
            raise self.erro(
                no,
                f"O campo '{no.id}' ({self._nao_utilizaveis[no.id]}) "
                "não pode ser usado em fórmulas.",
            )
        raise self.erro(no, f"O campo '{no.id}' não existe nesta definição.")

    def _tipo_binario(self, no: ast.BinOp) -> TipoFormula:
        esquerda, direita = self.tipo_de(no.left), self.tipo_de(no.right)
        operador = type(no.op)
        if esquerda is TipoFormula.NUMERO and direita is TipoFormula.NUMERO:
            return TipoFormula.NUMERO
        if esquerda is TipoFormula.DATA and operador in (ast.Add, ast.Sub):
            if direita is TipoFormula.DURACAO:
                return TipoFormula.DATA
            if direita is TipoFormula.DATA and operador is ast.Sub:
                return TipoFormula.NUMERO  # diferença em dias
        raise self.erro(
            no,
            f"A operação '{_SIMBOLOS_DE_OPERADOR[operador]}' não é permitida entre "
            f"{_ROTULOS_DOS_TIPOS[esquerda]} e {_ROTULOS_DOS_TIPOS[direita]}.",
        )

    def _tipo_unario(self, no: ast.UnaryOp) -> TipoFormula:
        tipo = self.tipo_de(no.operand)
        if isinstance(no.op, ast.USub):
            if tipo is not TipoFormula.NUMERO:
                raise self.erro(
                    no, f"O sinal de menos só se aplica a números, mas o valor é {_rotulo(tipo)}."
                )
            return TipoFormula.NUMERO
        if tipo is not TipoFormula.BOOLEANO:
            raise self.erro(no, f"'not' só se aplica a sim/não, mas o valor é {_rotulo(tipo)}.")
        return TipoFormula.BOOLEANO

    def _tipo_booleano(self, no: ast.BoolOp) -> TipoFormula:
        palavra = "and" if isinstance(no.op, ast.And) else "or"
        for operando in no.values:
            tipo = self.tipo_de(operando)
            if tipo is not TipoFormula.BOOLEANO:
                raise self.erro(
                    operando,
                    f"'{palavra}' só combina comparações ou valores de sim/não, "
                    f"mas recebeu {_rotulo(tipo)}.",
                )
        return TipoFormula.BOOLEANO

    def _tipo_de_comparacao(self, no: ast.Compare) -> TipoFormula:
        esquerda, direita = self.tipo_de(no.left), self.tipo_de(no.comparators[0])
        operador = type(no.ops[0])
        if esquerda is direita and esquerda in (TipoFormula.NUMERO, TipoFormula.DATA):
            return TipoFormula.BOOLEANO
        if esquerda is direita is TipoFormula.BOOLEANO and operador in (ast.Eq, ast.NotEq):
            return TipoFormula.BOOLEANO
        raise self.erro(
            no,
            f"Não é possível comparar {_rotulo(esquerda)} com {_rotulo(direita)} "
            f"usando '{_SIMBOLOS_DE_OPERADOR[operador]}'.",
        )

    def _tipo_da_chamada(self, no: ast.Call) -> TipoFormula:
        assert isinstance(no.func, ast.Name)  # o parser só deixa passar chamada por nome
        funcao = FUNCOES[no.func.id]
        tipos = [self.tipo_de(argumento) for argumento in no.args]
        resultado = funcao.inferir_tipo(tipos)
        # `TipoFormula` também é `str` (StrEnum), então o teste é pelo tipo, não por `str`.
        if not isinstance(resultado, TipoFormula):
            raise self.erro(no, resultado)
        if funcao.nome == "dias":
            self._exigir_dias_inteiros(no.args[0])
        return resultado

    def _exigir_dias_inteiros(self, argumento: ast.expr) -> None:
        """Constante não inteira em dias(...) é erro ao publicar; valor de campo só na execução."""
        constante = _constante_numerica(argumento)
        if constante is not None and constante != constante.to_integral_value():
            raise self.erro(
                argumento, f"dias() exige um número inteiro de dias, mas recebeu {constante}."
            )


def _rotulo(tipo: TipoFormula) -> str:
    return _ROTULOS_DOS_TIPOS[tipo]


def _constante_numerica(no: ast.expr) -> Decimal | None:
    if isinstance(no, ast.Constant) and type(no.value) in (int, float):
        return Decimal(str(no.value))
    if isinstance(no, ast.UnaryOp) and isinstance(no.op, ast.USub):
        interno = _constante_numerica(no.operand)
        return None if interno is None else -interno
    return None


# --- dependências entre campos calculados ---


def nomes_usados(formula: Formula) -> tuple[str, ...]:
    """Nomes de campo usados, na ordem do texto e sem repetir; `pi` é constante, não campo."""
    arvore = formula.arvore.body
    # O nome de uma função chamada (`se` em `se(...)`) é um `Name` na árvore, mas não é campo.
    funcoes_chamadas = {id(no.func) for no in ast.walk(arvore) if isinstance(no, ast.Call)}
    nomes = [
        no for no in ast.walk(arvore) if isinstance(no, ast.Name) and id(no) not in funcoes_chamadas
    ]
    nomes.sort(key=lambda no: (no.lineno, no.col_offset))
    return tuple(dict.fromkeys(no.id for no in nomes if no.id not in CONSTANTES))


def ordenar_calculados(dependencias: Mapping[str, Sequence[str]]) -> list[str]:
    """Ordem de cálculo (origens primeiro) dos campos calculados, ou `CicloDeDependencia`.

    `dependencias` mapeia cada calculado aos nomes que a fórmula usa; nomes que não são
    calculados (entradas, compartilhados) não entram no grafo. A ordem é determinística:
    segue a ordem do mapa e a ordem dos nomes em cada fórmula.
    """
    visitando, concluidos = set[str](), set[str]()
    ordem: list[str] = []

    for raiz in dependencias:
        if raiz in concluidos:
            continue
        # DFS iterativo: uma cadeia longa de campos não pode estourar a pilha de chamadas.
        caminho = [raiz]
        pilha = [(raiz, iter(dependencias[raiz]))]
        visitando.add(raiz)
        while pilha:
            no, vizinhos = pilha[-1]
            for vizinho in vizinhos:
                if vizinho not in dependencias or vizinho in concluidos:
                    continue
                if vizinho in visitando:
                    inicio = caminho.index(vizinho)
                    raise CicloDeDependencia((*caminho[inicio:], vizinho))
                visitando.add(vizinho)
                caminho.append(vizinho)
                pilha.append((vizinho, iter(dependencias[vizinho])))
                break
            else:
                pilha.pop()
                caminho.pop()
                visitando.discard(no)
                concluidos.add(no)
                ordem.append(no)
    return ordem


# --- avaliação ---

_OPERACOES_BINARIAS: dict[type[ast.operator], Callable[[Valor, Valor], Valor]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_COMPARACOES: dict[type[ast.cmpop], Callable[[Valor, Valor], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def avaliar(formula: Formula, valores: Mapping[str, Valor]) -> Valor:
    """Calcula a fórmula já verificada (e com tipos conferidos ao publicar).

    `valores` traz os campos já tipados (`Decimal`, `date`, `bool`); nome ausente é vazio.
    Falha de execução vira `ErroDeCalculo` com mensagem em PT-BR.
    """
    with localcontext(CONTEXTO_DECIMAL):
        try:
            return _Avaliador(formula.texto, valores).valor_de(formula.arvore.body)
        except ZeroDivisionError as erro:
            raise ErroDeCalculo("Divisão por zero.") from erro
        except Overflow as erro:
            raise ErroDeCalculo("O resultado é grande demais para ser calculado.") from erro
        except InvalidOperation as erro:
            # 0/0 também chega como InvalidOperation, com DivisionUndefined na lista de causas.
            if erro.args and DivisionUndefined in erro.args[0]:
                raise ErroDeCalculo("Divisão por zero.") from erro
            raise ErroDeCalculo(
                "Operação matemática inválida (por exemplo, raiz de número negativo)."
            ) from erro
        except OverflowError as erro:
            raise ErroDeCalculo(
                "O resultado ficou fora do intervalo de datas ou de dias permitido."
            ) from erro


class _Avaliador:
    def __init__(self, texto: str, valores: Mapping[str, Valor]) -> None:
        self._texto = texto
        self._valores = valores

    def valor_de(self, no: ast.expr) -> Valor:
        if isinstance(no, ast.Constant):
            return self._constante(no)
        if isinstance(no, ast.Name):
            return CONSTANTES[no.id].valor if no.id in CONSTANTES else self._valores.get(no.id)
        if isinstance(no, ast.BinOp):
            return self._binario(no)
        if isinstance(no, ast.UnaryOp):
            operando = self.valor_de(no.operand)
            if operando is None:
                return None
            return -operando if isinstance(no.op, ast.USub) else not operando
        if isinstance(no, ast.BoolOp):
            operandos = [self.valor_de(valor) for valor in no.values]
            if any(operando is None for operando in operandos):
                return None
            return all(operandos) if isinstance(no.op, ast.And) else any(operandos)
        if isinstance(no, ast.Compare):
            esquerda, direita = self.valor_de(no.left), self.valor_de(no.comparators[0])
            if esquerda is None or direita is None:
                return None
            return _COMPARACOES[type(no.ops[0])](esquerda, direita)
        if isinstance(no, ast.Call):
            assert isinstance(no.func, ast.Name)  # o parser só deixa passar chamada por nome
            argumentos = [partial(self.valor_de, argumento) for argumento in no.args]
            return FUNCOES[no.func.id].calcular(argumentos)
        raise ErroDeCalculo(f"Construção não prevista na fórmula ({type(no).__name__}).")

    def _constante(self, no: ast.Constant) -> Valor:
        if isinstance(no.value, bool):
            return no.value
        if isinstance(no.value, int):
            return Decimal(no.value)
        # `0.1` chega do `ast` como float. O Decimal nasce do texto original, não do float,
        # senão o ruído binário entraria no cálculo (§7).
        trecho = ast.get_source_segment(self._texto, no)
        try:
            return Decimal(trecho) if trecho is not None else Decimal(str(no.value))
        except InvalidOperation:
            return Decimal(str(no.value))

    def _binario(self, no: ast.BinOp) -> Valor:
        esquerda, direita = self.valor_de(no.left), self.valor_de(no.right)
        if esquerda is None or direita is None:
            return None
        resultado = _OPERACOES_BINARIAS[type(no.op)](esquerda, direita)
        # O Decimal devolve Infinity para `0 ** -1` sem levantar nada; um infinito não pode
        # virar valor de campo.
        if isinstance(resultado, Decimal) and not resultado.is_finite():
            raise ErroDeCalculo(
                "O resultado não é um número finito (por exemplo, zero elevado a potência "
                "negativa)."
            )
        # data - data dá um timedelta; a fórmula enxerga o número de dias.
        if isinstance(resultado, timedelta):
            return Decimal(resultado.days)
        return resultado


# --- cálculo dos campos de um registro ---


@dataclass(frozen=True)
class ValorDeCampo:
    """Valor já tipado de um campo, com o erro dele quando houver (campos compartilhados)."""

    valor: Valor = None
    erro: str | None = None


def calcular_campos(
    campos: Sequence[Campo],
    entradas: Mapping[str, Valor],
    compartilhados: Mapping[str, ValorDeCampo] | None = None,
) -> dict[str, ResultadoCalculado]:
    """Calcula todos os campos `calculado` e devolve `{valor, erro}` de cada um (§7).

    É a única função de cálculo: salvar registro e prévia chamam esta. `entradas` traz os
    campos de entrada já normalizados; `compartilhados`, os campos `ref__campo` da origem.
    Um erro num campo não impede o cálculo dos outros; quem depende dele herda o erro.
    """
    compartilhados = compartilhados or {}
    formulas = {
        campo.id: carregar_formula(campo.formula or "")
        for campo in campos
        if campo.tipo is TipoCampo.CALCULADO
    }
    nomes = {id_do_campo: nomes_usados(formula) for id_do_campo, formula in formulas.items()}

    resultados: dict[str, ValorDeCampo] = {}
    for id_do_campo in ordenar_calculados(nomes):
        resultados[id_do_campo] = _calcular_um(
            formulas[id_do_campo], nomes[id_do_campo], entradas, compartilhados, resultados
        )
    return {id_do_campo: _para_resultado(resultados[id_do_campo]) for id_do_campo in formulas}


def _calcular_um(
    formula: Formula,
    nomes: Sequence[str],
    entradas: Mapping[str, Valor],
    compartilhados: Mapping[str, ValorDeCampo],
    resultados: Mapping[str, ValorDeCampo],
) -> ValorDeCampo:
    valores: dict[str, Valor] = {}
    for nome in nomes:
        origem = resultados.get(nome) or compartilhados.get(nome)
        if origem is None:
            valores[nome] = entradas.get(nome)
        elif origem.erro is not None:
            return ValorDeCampo(None, f"Erro no campo '{nome}': {origem.erro}")
        else:
            valores[nome] = origem.valor

    try:
        valor = avaliar(formula, valores)
    except ErroDeCalculo as erro:
        return ValorDeCampo(None, str(erro))
    if isinstance(valor, timedelta):
        return ValorDeCampo(None, "O resultado é uma duração e não pode ser guardado no campo.")
    return ValorDeCampo(valor)


def _para_resultado(campo: ValorDeCampo) -> ResultadoCalculado:
    """Formato guardado e devolvido: número e data como string (§7); "f" evita `1E+3`."""
    valor = campo.valor
    if isinstance(valor, Decimal):
        return ResultadoCalculado(format(valor, "f"), campo.erro)
    if isinstance(valor, date):
        return ResultadoCalculado(valor.isoformat(), campo.erro)
    return ResultadoCalculado(valor, campo.erro)
