"""Análise de fórmulas: lê o texto e valida a árvore sem nunca executá-lo (AGENTS.md §7).

Nada aqui usa `eval`, `exec` nem `compile`: o texto só vira árvore (`ast.parse`) e cada nó
dela precisa estar numa lista de permissão.
"""

import ast

from forms.models import FormulaInvalida, Posicao

# Provisória: a tabela única de funções (e a aridade de cada uma) nasce na issue de funções,
# e este conjunto passa a ser derivado dela, para não existir uma lista paralela.
FUNCOES_PERMITIDAS = frozenset({"se", "min", "max", "media", "soma", "dias"})

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

    problema = _procurar_problema(arvore)
    if problema is not None:
        no, mensagem = problema
        raise FormulaInvalida(mensagem, _posicao_do_no(texto, no))
    return arvore


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
    if chamada.func.id not in FUNCOES_PERMITIDAS:
        return chamada, f"Função '{chamada.func.id}' não permitida na fórmula."
    if chamada.keywords or any(isinstance(argumento, ast.Starred) for argumento in chamada.args):
        return chamada, "Não são permitidos argumentos nomeados nem com * nas chamadas."
    return None


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
