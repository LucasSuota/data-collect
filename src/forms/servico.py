"""Casos de uso: o ponto de entrada comum de `api.py` e `cli.py` (AGENTS.md §5.1).

Toda regra de negócio fica aqui e abaixo. Quem chama passa a conexão e o relógio; este módulo
controla a transação, então cada caso de uso grava tudo ou nada.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

from forms import repositorio, validacao
from forms.formulas import CONSTANTES, FUNCOES, NOMES_RESERVADOS, ordenar_calculados
from forms.models import (
    CicloDeDependencia,
    Definicao,
    DefinicaoInvalida,
    ErroDeCampo,
    ErrosDoFormulario,
    Formulario,
    LoteInvalido,
    NaoEncontrado,
    ValorJson,
    Versao,
)
from forms.repositorio import ResumoDeFormulario, ResumoDeVersao, chave_do_nome
from forms.servico_anexos import guardar_anexo, ler_anexo, limpar_anexos_orfaos
from forms.servico_base import (
    compartilhados_publicados,
    origens_publicadas,
    referencias_brutas,
    transacao,
)
from forms.servico_consulta import (
    LIMITE_MAXIMO,
    LIMITE_PADRAO,
    ListagemDeRegistros,
    exportar_csv,
    listar_registros,
)
from forms.servico_pastas import (
    atualizar_pasta,
    conferir_destino,
    criar_pasta,
    excluir_pasta,
    listar_pastas,
    mover_formulario,
)
from forms.servico_registros import (
    ResultadoDaPrevia,
    atualizar_registro,
    criar_registro,
    excluir_formulario,
    excluir_registro,
    obter_registro,
    previa,
)
from forms.tipos_campo import ESPECIFICACOES, PROPRIEDADES_COMUNS
from forms.validacao import CampoCompartilhado

# O tipo da conexão, para quem chama o `servico` sem importar `sqlite3` (a CLI, por exemplo).
Conexao = sqlite3.Connection

# --- tipos de entrada e saída ---


@dataclass(frozen=True)
class Rascunho:
    """Formulário ainda não publicado. `definicao` é JSON não confiável, validado ao publicar."""

    nome: str
    definicao: ValorJson


@dataclass(frozen=True)
class FormularioCriado:
    formulario: Formulario
    versao: Versao


@dataclass(frozen=True)
class FormularioComVersao:
    formulario: Formulario
    versao_atual: Versao


@dataclass(frozen=True)
class ResultadoDaValidacao:
    valida: bool
    erros: tuple[ErroDeCampo, ...]


@dataclass(frozen=True)
class TipoDoCatalogo:
    id: str
    rotulo: str
    propriedades: tuple[str, ...]


@dataclass(frozen=True)
class FuncaoDoCatalogo:
    nome: str
    assinatura: str
    descricao: str
    exemplo: str


@dataclass(frozen=True)
class ConstanteDoCatalogo:
    nome: str
    valor: str
    tipo: str
    descricao: str


@dataclass(frozen=True)
class Catalogo:
    tipos: tuple[TipoDoCatalogo, ...]
    funcoes: tuple[FuncaoDoCatalogo, ...]
    constantes: tuple[ConstanteDoCatalogo, ...]
    nomes_reservados: tuple[str, ...]


# --- banco e leitura ---


def abrir_banco(caminho: Path | str) -> Conexao:
    """Abre (e cria, se preciso) o banco, com o esquema migrado para a versão atual."""
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    return repositorio.abrir_conexao(caminho)


def localizar_formulario(conexao: Conexao, referencia: str) -> FormularioComVersao:
    """Formulário pelo `id` (só dígitos) ou pelo nome (sem diferenciar caixa nem espaços)."""
    if referencia.strip().isdigit():
        return obter_formulario(conexao, int(referencia))
    formulario = repositorio.obter_formulario_por_nome(conexao, referencia)
    if formulario is None:
        raise NaoEncontrado(f"Formulário '{referencia}' não encontrado.")
    return obter_formulario(conexao, formulario.id)


def listar_formularios(conexao: sqlite3.Connection) -> list[ResumoDeFormulario]:
    return repositorio.listar_formularios(conexao)


def obter_formulario(conexao: sqlite3.Connection, formulario_id: int) -> FormularioComVersao:
    """O formulário com a versão atual completa: é de onde o front tira o `versao_id`."""
    return FormularioComVersao(
        formulario=repositorio.obter_formulario(conexao, formulario_id),
        versao_atual=repositorio.obter_versao_atual(conexao, formulario_id),
    )


def listar_versoes(conexao: sqlite3.Connection, formulario_id: int) -> list[ResumoDeVersao]:
    repositorio.obter_formulario(conexao, formulario_id)  # 404 se o formulário não existe
    return repositorio.listar_versoes(conexao, formulario_id)


def obter_versao(conexao: sqlite3.Connection, formulario_id: int, versao_id: int) -> Versao:
    """Versão com a definição, para renderizar um registro antigo."""
    return repositorio.obter_versao(conexao, versao_id, formulario_id)


# --- catálogo e validação sem estado ---


def catalogo() -> Catalogo:
    """Tipos de campo e funções de fórmula, lidos das mesmas tabelas que o avaliador usa."""
    return Catalogo(
        tipos=tuple(
            TipoDoCatalogo(
                id=especificacao.tipo.value,
                rotulo=especificacao.rotulo,
                propriedades=(*PROPRIEDADES_COMUNS, *especificacao.propriedades),
            )
            for especificacao in ESPECIFICACOES.values()
        ),
        funcoes=tuple(
            FuncaoDoCatalogo(f.nome, f.assinatura, f.descricao, f.exemplo) for f in FUNCOES.values()
        ),
        constantes=tuple(
            ConstanteDoCatalogo(c.nome, format(c.valor, "f"), c.tipo.value, c.descricao)
            for c in CONSTANTES.values()
        ),
        nomes_reservados=tuple(sorted(NOMES_RESERVADOS)),
    )


def validar_definicao(conexao: sqlite3.Connection, definicao: ValorJson) -> ResultadoDaValidacao:
    """Sem estado: não exige formulário criado. Definição incompleta é o caso normal enquanto o
    usuário edita, então devolve os erros (todos) em vez de levantar."""
    origens = origens_publicadas(conexao, referencias_brutas(definicao), {})
    erros = validacao.validar_definicao(definicao, origens)
    return ResultadoDaValidacao(valida=not erros, erros=erros)


# --- criar e publicar ---


def criar_formulario(
    conexao: sqlite3.Connection,
    nome: str,
    definicao: ValorJson,
    agora: datetime,
    pasta_id: int | None = None,
) -> FormularioCriado:
    """Cria o formulário e já publica a versão 1: um formulário sem versão não pode ser
    preenchido, então esse estado não existe. Definição inválida não cria nada.
    `pasta_id` (opcional) já põe o formulário numa pasta; nulo é a raiz (§2.10)."""
    with transacao(conexao):
        conferir_destino(conexao, pasta_id, "pasta_id")
        conjunto = _validar_conjunto(conexao, [Rascunho(nome, definicao)])
        item = conjunto.itens[0]
        if item.erros:
            raise DefinicaoInvalida(tuple(item.erros))
        criado = _gravar(conexao, conjunto, agora, versionando=None)[0]
        if pasta_id is not None:
            repositorio.mover_formulario(conexao, criado.formulario.id, pasta_id)
            return FormularioCriado(replace(criado.formulario, pasta_id=pasta_id), criado.versao)
        return criado


def duplicar_formulario(
    conexao: sqlite3.Connection, formulario_id: int, nome: str | None, agora: datetime
) -> FormularioCriado:
    """Cria um formulário novo com a v1 igual à definição da versão atual do original (§2.10).

    A cópia nasce na mesma pasta, sem registros e sem o histórico de versões; passa pela mesma
    publicação de `criar_formulario`, então valida e registra as dependências (a cópia depende das
    mesmas origens do original, e quem dependia do original não passa a depender dela).
    Sem `nome`, o padrão é `<nome> (cópia)`; um `nome` informado e repetido é erro no campo.
    """
    original = repositorio.obter_formulario(conexao, formulario_id)
    definicao = repositorio.obter_versao_atual(conexao, formulario_id).definicao
    if nome is None:
        nome = _nome_livre_da_copia(conexao, original.nome)
    return criar_formulario(conexao, nome, definicao.para_json(), agora, original.pasta_id)


def _nome_livre_da_copia(conexao: sqlite3.Connection, nome: str) -> str:
    """`<nome> (cópia)`, depois `(cópia 2)`, `(cópia 3)`… até achar um que não exista."""
    candidato = f"{nome} (cópia)"
    numero = 1
    while repositorio.obter_formulario_por_nome(conexao, candidato) is not None:
        numero += 1
        candidato = f"{nome} (cópia {numero})"
    return candidato


def publicar_versao(
    conexao: sqlite3.Connection, formulario_id: int, definicao: ValorJson, agora: datetime
) -> Versao:
    """Publica a próxima versão (anterior + 1). A publicada nunca é alterada."""
    formulario = repositorio.obter_formulario(conexao, formulario_id)
    with transacao(conexao):
        conjunto = _validar_conjunto(
            conexao, [Rascunho(formulario.nome, definicao)], versionando=formulario
        )
        item = conjunto.itens[0]
        if item.erros:
            raise DefinicaoInvalida(tuple(item.erros))
        return _gravar(conexao, conjunto, agora, versionando=formulario)[0].versao


def validar_conjunto(
    conexao: sqlite3.Connection, rascunhos: Sequence[Rascunho]
) -> list[ErrosDoFormulario]:
    """Valida formulários ainda não publicados que podem se referenciar entre si, sem gravar.

    É o que o lote e o gerador por IA usam. Devolve só os formulários com erro.
    """
    return _erros_do_conjunto(_validar_conjunto(conexao, rascunhos))


def criar_formularios_em_lote(
    conexao: sqlite3.Connection, rascunhos: Sequence[Rascunho], agora: datetime
) -> list[FormularioCriado]:
    """Cria todos numa só transação, origem primeiro, cada um com a versão 1. Qualquer erro
    levanta `LoteInvalido` e não cria nada. Independe da ordem de entrada."""
    if not rascunhos:
        return []
    with transacao(conexao):
        conjunto = _validar_conjunto(conexao, rascunhos)
        erros = _erros_do_conjunto(conjunto)
        if erros:
            raise LoteInvalido(tuple(erros))
        return _gravar(conexao, conjunto, agora, versionando=None)


# --- templates ---


def importar_template(
    conexao: sqlite3.Connection, caminho: Path, agora: datetime, nome: str | None = None
) -> FormularioCriado:
    """Cria um formulário a partir de um arquivo de definição (por exemplo, `templates/*.json`).

    O nome do formulário é o do arquivo (ou `nome`). É o nome que as referências de outros
    templates usam, então um template dependente precisa que a origem já exista; para importar
    vários que dependem uns dos outros, use `importar_templates`.
    """
    rascunho = ler_template(caminho, nome)
    return criar_formulario(conexao, rascunho.nome, rascunho.definicao, agora)


def importar_templates(
    conexao: sqlite3.Connection, caminhos: Sequence[Path], agora: datetime
) -> list[FormularioCriado]:
    """Importa vários templates de uma vez, numa transação, origem primeiro (qualquer ordem)."""
    return criar_formularios_em_lote(conexao, [ler_template(c) for c in caminhos], agora)


def ler_template(caminho: Path, nome: str | None = None) -> Rascunho:
    try:
        texto = caminho.read_text(encoding="utf-8")
    except FileNotFoundError as erro:
        raise NaoEncontrado(f"Template '{caminho.name}' não encontrado.") from erro
    try:
        definicao = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise DefinicaoInvalida(
            (ErroDeCampo("arquivo", f"O template '{caminho.name}' não é um JSON válido: {erro}."),)
        ) from erro
    return Rascunho(nome or caminho.stem, definicao)


# --- o motor: valida um conjunto de rascunhos (publicar um formulário é o conjunto de 1) ---


@dataclass
class _Item:
    rascunho: Rascunho
    chave: str
    referencias: list[tuple[str, str]]  # (id do campo, nome do formulário de origem)
    erros: list[ErroDeCampo] = field(default_factory=list)
    definicao: Definicao | None = None
    compartilhados: dict[str, CampoCompartilhado] | None = None


@dataclass
class _Conjunto:
    itens: list[_Item]  # na ordem de entrada
    ordem: list[_Item]  # na ordem de criação: as origens antes de quem depende delas


def _validar_conjunto(
    conexao: sqlite3.Connection,
    rascunhos: Sequence[Rascunho],
    versionando: Formulario | None = None,
) -> _Conjunto:
    """`versionando` é o formulário que ganha uma nova versão; sem ele, todos são novos."""
    itens = [_Item(r, chave_do_nome(r.nome), referencias_brutas(r.definicao)) for r in rascunhos]
    por_chave = _validar_nomes(conexao, itens, versionando)
    ordem = _ordenar(itens, por_chave)
    cache: dict[int, dict[str, CampoCompartilhado]] = {}

    for item in ordem:
        _analisar_item(conexao, item, por_chave, cache)
        if versionando is not None:
            _conferir_ciclo_com_dependentes(conexao, item, versionando)
            if item.compartilhados is not None:
                _conferir_contrato(conexao, item, versionando, cache)
    return _Conjunto(itens, ordem)


def _validar_nomes(
    conexao: sqlite3.Connection, itens: Sequence[_Item], versionando: Formulario | None
) -> dict[str, _Item]:
    """Devolve o primeiro item de cada nome; os repetidos ganham erro no campo `nome`."""
    por_chave: dict[str, _Item] = {}
    for item in itens:
        if not item.rascunho.nome.strip():
            item.erros.append(ErroDeCampo("nome", "O nome do formulário é obrigatório."))
        elif item.chave in por_chave:
            item.erros.append(ErroDeCampo("nome", "Já existe um formulário com este nome no lote."))
        elif versionando is None and repositorio.obter_formulario_por_nome(
            conexao, item.rascunho.nome
        ):
            item.erros.append(ErroDeCampo("nome", "Já existe um formulário com este nome."))
        por_chave.setdefault(item.chave, item)
    return por_chave


def _ordenar(itens: Sequence[_Item], por_chave: Mapping[str, _Item]) -> list[_Item]:
    """Origens antes dos dependentes. Ciclo entre rascunhos vira erro (e fica de fora)."""
    primeiros = [item for item in itens if por_chave[item.chave] is item]
    grafo = {
        item.chave: [
            chave for _, nome in item.referencias if (chave := chave_do_nome(nome)) in por_chave
        ]
        for item in primeiros
    }
    while True:
        try:
            ordem_das_chaves = ordenar_calculados(grafo)
            break
        except CicloDeDependencia as ciclo:
            _registrar_ciclo(ciclo.campos, por_chave)
            # Tira do grafo só quem está no ciclo; os demais continuam sendo validados.
            grafo = {c: ds for c, ds in grafo.items() if c not in ciclo.campos}
    repetidos = [item for item in itens if por_chave[item.chave] is not item]
    return [por_chave[chave] for chave in ordem_das_chaves] + repetidos


def _registrar_ciclo(caminho: Sequence[str], por_chave: Mapping[str, _Item]) -> None:
    nomes = " → ".join(por_chave[chave].rascunho.nome.strip() for chave in caminho)
    mensagem = f"Dependência circular entre os formulários: {nomes}."
    for origem, destino in zip(caminho, caminho[1:], strict=False):
        item = por_chave[origem]
        campo_id = next(campo for campo, nome in item.referencias if chave_do_nome(nome) == destino)
        item.erros.append(ErroDeCampo(f"{campo_id}.formulario", mensagem))


def _analisar_item(
    conexao: sqlite3.Connection,
    item: _Item,
    por_chave: Mapping[str, _Item],
    cache: dict[int, dict[str, CampoCompartilhado]],
) -> None:
    origens: dict[str, Mapping[str, CampoCompartilhado]] = {}
    for _, nome in item.referencias:
        origem = por_chave.get(chave_do_nome(nome))
        if origem is not None:
            if origem.compartilhados is None:
                # A origem tem erro (ou está num ciclo): apontar campo "não compartilhado"
                # aqui seria ruído. Corrigir a origem primeiro resolve.
                item.erros.append(
                    ErroDeCampo(
                        "campos",
                        f"Corrija primeiro o formulário '{origem.rascunho.nome.strip()}', "
                        "do qual este depende.",
                    )
                )
                return
            origens[nome] = origem.compartilhados
        else:
            publicado = repositorio.obter_formulario_por_nome(conexao, nome)
            if publicado is not None:
                origens[nome] = compartilhados_publicados(conexao, publicado, cache)

    analise = validacao.analisar_definicao(item.rascunho.definicao, origens)
    item.erros.extend(analise.erros)
    if analise.definicao is not None:
        item.definicao = analise.definicao
        item.compartilhados = validacao.compartilhados_da_definicao(
            analise.definicao, analise.tipos_calculados
        )


def _conferir_ciclo_com_dependentes(
    conexao: sqlite3.Connection, item: _Item, versionando: Formulario
) -> None:
    """A nova versão de uma origem não pode passar a depender de quem já depende dela."""
    dependentes = set(repositorio.formularios_dependentes(conexao, versionando.id, transitivo=True))
    for campo_id, nome in item.referencias:
        alvo = repositorio.obter_formulario_por_nome(conexao, nome)
        if alvo is not None and alvo.id in dependentes:
            item.erros.append(
                ErroDeCampo(
                    f"{campo_id}.formulario",
                    f"Dependência circular entre os formulários: {versionando.nome} → "
                    f"{alvo.nome} → {versionando.nome}. '{alvo.nome}' já depende de "
                    f"'{versionando.nome}' (direta ou indiretamente).",
                )
            )


def _conferir_contrato(
    conexao: sqlite3.Connection,
    item: _Item,
    formulario: Formulario,
    cache: dict[int, dict[str, CampoCompartilhado]],
) -> None:
    """Enquanto houver dependentes, a nova versão não quebra os campos compartilhados (§2.7)."""
    nomes = sorted(
        repositorio.obter_formulario(conexao, i).nome
        for i in repositorio.formularios_dependentes(conexao, formulario.id, transitivo=False)
    )
    if not nomes or item.compartilhados is None or item.definicao is None:
        return
    usados_por = ", ".join(f"'{nome}'" for nome in nomes)
    ids_novos = {campo.id for campo in item.definicao.campos}
    antigos = compartilhados_publicados(conexao, formulario, cache)

    for id_do_campo, antigo in antigos.items():
        novo = item.compartilhados.get(id_do_campo)
        if novo is None and id_do_campo not in ids_novos:
            item.erros.append(
                ErroDeCampo(
                    id_do_campo,
                    f"O campo '{id_do_campo}' é compartilhado com {usados_por} "
                    "e não pode ser removido.",
                )
            )
        elif novo is None:
            item.erros.append(
                ErroDeCampo(
                    f"{id_do_campo}.compartilhado",
                    f"O campo '{id_do_campo}' é usado por {usados_por} "
                    "e precisa continuar compartilhado.",
                )
            )
        elif novo.tipo != antigo.tipo:
            item.erros.append(
                ErroDeCampo(
                    f"{id_do_campo}.tipo",
                    f"O campo '{id_do_campo}' é usado por {usados_por} e não pode mudar de tipo "
                    f"(de {antigo.tipo.value} para {novo.tipo.value}).",
                )
            )
        elif novo.tipo_na_formula != antigo.tipo_na_formula:
            item.erros.append(
                ErroDeCampo(
                    f"{id_do_campo}.formula",
                    f"O campo calculado '{id_do_campo}' é usado por {usados_por} e o tipo do seu "
                    f"resultado não pode mudar (de {_nome_do_tipo(antigo)} para "
                    f"{_nome_do_tipo(novo)}).",
                )
            )


def _nome_do_tipo(campo: CampoCompartilhado) -> str:
    return "sem tipo" if campo.tipo_na_formula is None else campo.tipo_na_formula.value


def _erros_do_conjunto(conjunto: _Conjunto) -> list[ErrosDoFormulario]:
    return [
        ErrosDoFormulario(item.rascunho.nome, tuple(item.erros))
        for item in conjunto.itens
        if item.erros
    ]


def _gravar(
    conexao: sqlite3.Connection,
    conjunto: _Conjunto,
    agora: datetime,
    versionando: Formulario | None,
) -> list[FormularioCriado]:
    """Grava na ordem de criação (origens primeiro) e registra as dependências."""
    criados: list[FormularioCriado] = []
    for item in conjunto.ordem:
        assert item.definicao is not None  # sem erros, todo item tem definição
        formulario = versionando or repositorio.criar_formulario(conexao, item.rascunho.nome, agora)
        versao = repositorio.inserir_versao(conexao, formulario.id, item.definicao, agora)
        origens = {
            origem.id
            for _, nome in item.referencias
            if (origem := repositorio.obter_formulario_por_nome(conexao, nome)) is not None
        }
        repositorio.registrar_dependencias(conexao, formulario.id, origens)
        criados.append(FormularioCriado(formulario, versao))
    return criados


# `api.py` e `cli.py` chamam tudo por aqui; cada grupo de casos de uso mora no seu módulo.
__all__ = [
    "FUNCOES",
    "Conexao",
    "LIMITE_MAXIMO",
    "LIMITE_PADRAO",
    "Catalogo",
    "FormularioComVersao",
    "FormularioCriado",
    "ListagemDeRegistros",
    "Rascunho",
    "ResultadoDaPrevia",
    "ResultadoDaValidacao",
    "abrir_banco",
    "atualizar_pasta",
    "atualizar_registro",
    "catalogo",
    "criar_formulario",
    "criar_formularios_em_lote",
    "criar_pasta",
    "criar_registro",
    "duplicar_formulario",
    "excluir_formulario",
    "excluir_pasta",
    "excluir_registro",
    "exportar_csv",
    "guardar_anexo",
    "importar_template",
    "importar_templates",
    "ler_anexo",
    "limpar_anexos_orfaos",
    "listar_formularios",
    "listar_pastas",
    "listar_registros",
    "listar_versoes",
    "localizar_formulario",
    "mover_formulario",
    "obter_formulario",
    "obter_registro",
    "obter_versao",
    "previa",
    "publicar_versao",
    "repositorio",
    "validar_conjunto",
    "validar_definicao",
]
