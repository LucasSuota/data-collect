"""Ferramentas determinísticas do chatbot (AGENTS.md §2.5, §3.3).

O LLM só **escolhe** a ferramenta e os **argumentos**; quem executa e calcula é o código, com
`Decimal`. Os argumentos são validados contra a definição do formulário (nome do campo, função
da lista, datas ISO) e nenhuma ferramenta aceita ou gera SQL. Campo com `"ia": false` e a
localização nunca saem daqui. Tudo roda com o contexto de quem perguntou (equipe e cargo).
"""

from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from forms import repositorio, servico
from forms.banco import Conexao
from forms.ia.indexacao import campos_da_ia
from forms.models import (
    Campo,
    NaoEncontrado,
    RegistroInvalido,
    TipoCampo,
    ValorInvalido,
    ValorJson,
    Versao,
)

LIMITE_DE_REGISTROS_LISTADOS = 20
TETO_DE_REGISTROS_NO_AGREGADO = 5000
FUNCOES = ("contagem", "soma", "media", "min", "max")

# O que cada ferramenta aceita: nome -> (descrição para o prompt, argumentos permitidos).
DESCRICAO_DAS_FERRAMENTAS = {
    "listar_formularios": "Lista os formulários da equipe. Sem argumentos.",
    "buscar_registros": (
        "Lista registros de um formulário. Argumentos: formulario (nome ou id), de e ate "
        "(AAAA-MM-DD, opcionais, sobre a data de criação), filtros (objeto campo->valor, "
        "opcional), limite (opcional, até 20)."
    ),
    "contar_registros": (
        "Conta registros de um formulário e quantos estão em cada estado. Argumentos: "
        "formulario, de, ate, filtros (como em buscar_registros)."
    ),
    "valor_do_campo": "Valor de um campo de um registro. Argumentos: registro_id, campo.",
    "agregar": (
        "Calcula contagem, soma, media, min ou max de um campo numérico. Argumentos: "
        "formulario, campo, funcao (contagem|soma|media|min|max), de, ate, filtros."
    ),
}
_ARGUMENTOS = {
    "listar_formularios": set(),
    "buscar_registros": {"formulario", "de", "ate", "filtros", "limite"},
    "contar_registros": {"formulario", "de", "ate", "filtros"},
    "valor_do_campo": {"registro_id", "campo"},
    "agregar": {"formulario", "campo", "funcao", "de", "ate", "filtros"},
}


def executar(conexao: Conexao, nome: str, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    """Roda a ferramenta. Argumento inválido → `ValorInvalido` (nunca executa o que não entende)."""
    if nome not in _ARGUMENTOS:
        raise ValorInvalido(f"Ferramenta desconhecida: {nome!r}.")
    desconhecidos = sorted(set(argumentos) - _ARGUMENTOS[nome])
    if desconhecidos:
        raise ValorInvalido(f"Argumento desconhecido em {nome}: {desconhecidos[0]!r}.")
    ferramenta: Callable[[Conexao, Mapping[str, object]], dict[str, ValorJson]] = _FERRAMENTAS[nome]
    return ferramenta(conexao, argumentos)


# --- leitura segura dos argumentos ---


def _formulario(conexao: Conexao, argumentos: Mapping[str, object]):
    referencia = argumentos.get("formulario")
    if (
        not isinstance(referencia, (str, int))
        or isinstance(referencia, bool)
        or not str(referencia).strip()
    ):
        raise ValorInvalido("Informe o formulário (nome ou id).")
    try:
        return servico.localizar_formulario(conexao, str(referencia))
    except NaoEncontrado as erro:
        raise ValorInvalido(str(erro)) from erro


def _data(argumentos: Mapping[str, object], nome: str) -> date | None:
    valor = argumentos.get(nome)
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError as erro:
        raise ValorInvalido(f"'{nome}' deve ser uma data AAAA-MM-DD.") from erro


def _filtros(argumentos: Mapping[str, object]) -> dict[str, str | bool]:
    bruto = argumentos.get("filtros") or {}
    if not isinstance(bruto, dict):
        raise ValorInvalido("'filtros' deve ser um objeto campo -> valor.")
    filtros: dict[str, str | bool] = {}
    for campo, valor in bruto.items():
        if not isinstance(valor, (str, bool)):
            raise ValorInvalido(f"O filtro de '{campo}' deve ser um texto ou verdadeiro/falso.")
        filtros[str(campo)] = valor
    return filtros


def _campo(versao: Versao, referencia: object) -> Campo:
    """O campo pelo id ou pelo rótulo; só entre os que a IA pode ver (§2.15)."""
    texto = str(referencia or "").strip()
    permitidos = campos_da_ia(versao)
    for campo in permitidos:
        if texto in (campo.id, campo.rotulo) or texto.casefold() == campo.rotulo.casefold():
            return campo
    raise ValorInvalido(f"O campo {texto!r} não existe ou não está disponível para a IA.")


def _versoes(conexao: Conexao, formulario_id: int) -> list[Versao]:
    return [
        repositorio.obter_versao(conexao, v.id)
        for v in repositorio.listar_versoes(conexao, formulario_id)
    ]


def _consulta(conexao: Conexao, formulario_id: int, versao_id: int, argumentos, **extras):
    try:
        return servico.listar_registros(
            conexao,
            formulario_id,
            versao_id=versao_id,
            filtros=_filtros(argumentos),
            criado_de=_data(argumentos, "de"),
            criado_ate=_data(argumentos, "ate"),
            **extras,
        )
    except RegistroInvalido as erro:
        raise ValorInvalido("; ".join(f"{e.campo}: {e.mensagem}" for e in erro.erros)) from erro


def _valor_bruto(campo: Campo, guardado: ValorJson) -> ValorJson:
    """O valor guardado, na precisão total: é o que os cálculos usam (§7)."""
    if campo.tipo is TipoCampo.CALCULADO:
        if not isinstance(guardado, dict):
            return None
        if guardado.get("erro"):
            return f"ERRO: {guardado['erro']}"
        return guardado.get("valor")
    return guardado


def _valor(campo: Campo, guardado: ValorJson) -> ValorJson:
    """O valor para mostrar: arredondado pelas `casas_decimais` do campo (só a exibição)."""
    return _arredondar(campo, _valor_bruto(campo, guardado))


def _arredondar(campo: Campo, valor: ValorJson) -> ValorJson:
    if campo.casas_decimais is None or not isinstance(valor, str):
        return valor
    try:
        return format(
            Decimal(valor).quantize(Decimal(1).scaleb(-campo.casas_decimais), ROUND_HALF_UP), "f"
        )
    except ArithmeticError:
        return valor


# --- as ferramentas ---


def _listar_formularios(conexao: Conexao, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    return {
        "formularios": [
            {"id": f.id, "nome": f.nome, "versao": f.versao_atual_numero}
            for f in servico.listar_formularios(conexao)
        ]
    }


def _buscar_registros(conexao: Conexao, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    formulario = _formulario(conexao, argumentos)
    limite = argumentos.get("limite", 10)
    if (
        not isinstance(limite, int)
        or isinstance(limite, bool)
        or not 1 <= limite <= LIMITE_DE_REGISTROS_LISTADOS
    ):
        raise ValorInvalido(f"'limite' deve estar entre 1 e {LIMITE_DE_REGISTROS_LISTADOS}.")
    achados: list[ValorJson] = []
    total = 0
    for versao in _versoes(conexao, formulario.formulario.id)[::-1]:
        listagem = _consulta(
            conexao, formulario.formulario.id, versao.id, argumentos, limite=limite - len(achados)
        )
        total += listagem.total
        campos = campos_da_ia(versao)
        for registro in listagem.itens:
            if len(achados) >= limite:
                break
            achados.append(
                {
                    "registro_id": registro.id,
                    "criado_em": registro.criado_em[:10],
                    "valores": {c.rotulo: _valor(c, registro.dados.get(c.id)) for c in campos},
                }
            )
    return {"formulario": formulario.formulario.nome, "total": total, "registros": achados}


def _contar_registros(conexao: Conexao, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    formulario = _formulario(conexao, argumentos)
    total = 0
    por_estado = {"conforme": 0, "nao_conforme": 0, "erro": 0, "aguardando": 0}
    for versao in _versoes(conexao, formulario.formulario.id):
        total += _consulta(conexao, formulario.formulario.id, versao.id, argumentos, limite=1).total
        try:
            contagens = servico.contar_por_estado(
                conexao,
                formulario.formulario.id,
                versao_id=versao.id,
                filtros=_filtros(argumentos),
                criado_de=_data(argumentos, "de"),
                criado_ate=_data(argumentos, "ate"),
            )
        except RegistroInvalido as erro:
            raise ValorInvalido("; ".join(e.mensagem for e in erro.erros)) from erro
        if contagens.campo_status is not None:
            for estado in por_estado:
                por_estado[estado] += getattr(contagens, estado)
    return {
        "formulario": formulario.formulario.nome,
        "total": total,
        "por_estado": dict(por_estado),
    }


def _valor_do_campo(conexao: Conexao, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    registro_id = argumentos.get("registro_id")
    if not isinstance(registro_id, int) or isinstance(registro_id, bool):
        raise ValorInvalido("'registro_id' deve ser um número inteiro.")
    try:
        registro = servico.obter_registro(conexao, registro_id)
    except NaoEncontrado as erro:
        raise ValorInvalido(str(erro)) from erro
    versao = repositorio.obter_versao(conexao, registro.versao_id)
    campo = _campo(versao, argumentos.get("campo"))
    return {
        "registro_id": registro.id,
        "campo": campo.rotulo,
        "unidade": campo.unidade,
        "valor": _valor(campo, registro.dados.get(campo.id)),
    }


def _agregar(conexao: Conexao, argumentos: Mapping[str, object]) -> dict[str, ValorJson]:
    formulario = _formulario(conexao, argumentos)
    funcao = argumentos.get("funcao")
    if funcao not in FUNCOES:
        raise ValorInvalido(f"'funcao' deve ser uma de: {', '.join(FUNCOES)}.")
    valores: list[Decimal] = []
    considerados = sem_valor = 0
    rotulo = unidade = None
    for versao in _versoes(conexao, formulario.formulario.id):
        try:
            campo = _campo(versao, argumentos.get("campo"))
        except ValorInvalido:
            continue  # esta versão não tem o campo
        if funcao != "contagem" and campo.tipo not in (TipoCampo.NUMERO, TipoCampo.CALCULADO):
            raise ValorInvalido(f"O campo {campo.rotulo!r} não é numérico.")
        rotulo, unidade = campo.rotulo, campo.unidade
        deslocamento = 0
        while considerados < TETO_DE_REGISTROS_NO_AGREGADO:
            pagina = _consulta(
                conexao,
                formulario.formulario.id,
                versao.id,
                argumentos,
                limite=servico.LIMITE_MAXIMO,
                deslocamento=deslocamento,
            )
            for registro in pagina.itens:
                considerados += 1
                valor = _valor_bruto(campo, registro.dados.get(campo.id))
                try:
                    valores.append(Decimal(str(valor)))
                except (ArithmeticError, ValueError):
                    sem_valor += 1
            deslocamento += servico.LIMITE_MAXIMO
            if deslocamento >= pagina.total:
                break
    if rotulo is None:
        raise ValorInvalido(
            f"O campo {argumentos.get('campo')!r} não existe ou não está disponível para a IA."
        )
    return {
        "formulario": formulario.formulario.nome,
        "campo": rotulo,
        "unidade": unidade,
        "funcao": str(funcao),
        "valor": _calcular(str(funcao), valores),
        "valor_para_exibir": _arredondar(campo, _calcular(str(funcao), valores)),
        "registros_com_valor": len(valores),
        "registros_sem_valor": sem_valor,
    }


def _calcular(funcao: str, valores: list[Decimal]) -> str | None:
    """O cálculo é do código, em `Decimal`: sem valores, o resultado é vazio, nunca zero."""
    if funcao == "contagem":
        return str(len(valores))
    if not valores:
        return None
    resultado = {
        "soma": sum(valores, Decimal(0)),
        "media": sum(valores, Decimal(0)) / len(valores),
        "min": min(valores),
        "max": max(valores),
    }[funcao]
    return format(resultado.normalize(), "f")


_FERRAMENTAS: dict[str, Callable[[Conexao, Mapping[str, object]], dict[str, ValorJson]]] = {
    "listar_formularios": _listar_formularios,
    "buscar_registros": _buscar_registros,
    "contar_registros": _contar_registros,
    "valor_do_campo": _valor_do_campo,
    "agregar": _agregar,
}


def catalogo_para_o_prompt(conexao: Conexao) -> str:
    """Formulários e campos (só os que a IA pode ver): metadados, nunca valores de registro."""
    linhas = []
    for resumo in servico.listar_formularios(conexao):
        if resumo.versao_atual_id is None:
            continue
        versao = repositorio.obter_versao(conexao, resumo.versao_atual_id)
        campos = ", ".join(f"{c.rotulo} ({c.tipo.value})" for c in campos_da_ia(versao))
        linhas.append(f"- {resumo.nome} (id {resumo.id}): {campos}")
    return "\n".join(linhas) or "(nenhum formulário)"
