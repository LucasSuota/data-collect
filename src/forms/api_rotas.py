"""Endpoints da API (AGENTS.md §2.2, §2.3, §2.8). Só traduz HTTP: nenhuma regra de negócio.

Cada rota chama uma função de `servico` e converte o resultado em modelo de resposta. As exceções
de domínio viram o status HTTP certo em `api.py`.
"""

import dataclasses
import re
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from forms import servico
from forms.api_dependencias import DepAgora, DepConexao, autorizar
from forms.api_esquemas import (
    CatalogoSaida,
    ContagensSaida,
    DuplicarEntrada,
    ErroDeCampoSaida,
    ErroSaida,
    ExibicaoSaida,
    FormularioDetalheSaida,
    FormularioEntrada,
    HistoricoSaida,
    ListagemDeRegistrosSaida,
    LoteEntrada,
    MoverFormularioEntrada,
    PastaAtualizacao,
    PastaEntrada,
    PastaSaida,
    PessoaResumoSaida,
    PreviaEntrada,
    PreviaSaida,
    RascunhoEntrada,
    RascunhoSaida,
    RegistroAtualizacao,
    RegistroEntrada,
    RegistroSaida,
    ResultadoCalculadoSaida,
    ResumoDeFormularioSaida,
    ResumoDeVersaoSaida,
    ValidarEntrada,
    ValidarSaida,
    VersaoEntrada,
    VersaoSaida,
    coluna_de,
)
from forms.banco import Conexao
from forms.models import ErroDeCampo, Formulario, Registro, RegistroInvalido, Versao
from forms.repositorio import RascunhoGuardado
from forms.servico import Rascunho

# Erros comuns a (quase) todo endpoint, para o OpenAPI mostrar o formato uniforme.
ERROS_COMUNS = {
    401: {"model": ErroSaida, "description": "Sem token, token inválido ou expirado."},
    403: {"model": ErroSaida, "description": "Sem permissão, sem equipe ou termos pendentes."},
    404: {"model": ErroSaida, "description": "Recurso inexistente."},
    422: {"model": ErroSaida, "description": "Dados inválidos, com os erros por campo."},
}
_ERRO_409 = {409: {"model": ErroSaida, "description": "Exclusão bloqueada por vínculo."}}

roteador = APIRouter(dependencies=[Depends(autorizar)], responses=ERROS_COMUNS)


# --- dependências (injetadas por parâmetro, nunca globais) ---


# --- formulários e versões ---


@roteador.post(
    "/formularios",
    status_code=201,
    response_model=FormularioDetalheSaida,
    tags=["formulários"],
    summary="Cria o formulário e publica a versão 1",
)
def criar_formulario(
    entrada: FormularioEntrada, conexao: DepConexao, agora: DepAgora
) -> FormularioDetalheSaida:
    criado = servico.criar_formulario(
        conexao, entrada.nome, entrada.definicao, agora, entrada.pasta_id
    )
    return _detalhe(criado.formulario, criado.versao)


@roteador.post(
    "/formularios/lote",
    status_code=201,
    response_model=list[ResumoDeFormularioSaida],
    tags=["formulários"],
    summary="Cria vários formulários numa só transação, origem primeiro",
    description=(
        "Os formulários do lote podem se referenciar entre si e a formulários já existentes, "
        "em qualquer ordem. Qualquer erro devolve 422 e **nada é criado**. Nos erros, o `campo` "
        "vem com o **nome do formulário como prefixo**: `proctor.umidade.formula`."
    ),
)
def criar_formularios_em_lote(
    entrada: LoteEntrada, conexao: DepConexao, agora: DepAgora
) -> list[ResumoDeFormularioSaida]:
    rascunhos = [Rascunho(f.nome, f.definicao) for f in entrada.formularios]
    criados = servico.criar_formularios_em_lote(conexao, rascunhos, agora)
    return [ResumoDeFormularioSaida.do_formulario(c.formulario, c.versao) for c in criados]


@roteador.get(
    "/formularios",
    response_model=list[ResumoDeFormularioSaida],
    tags=["formulários"],
    summary="Lista os formulários",
)
def listar_formularios(conexao: DepConexao) -> list[ResumoDeFormularioSaida]:
    return [ResumoDeFormularioSaida.de(r) for r in servico.listar_formularios(conexao)]


@roteador.get(
    "/formularios/{formulario_id}",
    response_model=FormularioDetalheSaida,
    tags=["formulários"],
    summary="Formulário com a versão atual completa",
)
def obter_formulario(formulario_id: int, conexao: DepConexao) -> FormularioDetalheSaida:
    detalhe = servico.obter_formulario(conexao, formulario_id)
    return _detalhe(detalhe.formulario, detalhe.versao_atual)


@roteador.post(
    "/formularios/{formulario_id}/duplicar",
    status_code=201,
    response_model=FormularioDetalheSaida,
    tags=["formulários"],
    summary="Duplica o formulário",
    description=(
        "Cria um formulário novo com a **versão 1 igual à definição da versão atual** do original, "
        "na mesma pasta e **sem registros**. O corpo é opcional: sem `nome`, o padrão é "
        '"<nome> (cópia)", depois "(cópia 2)"… Um `nome` repetido é 422 no campo `nome`.'
    ),
)
def duplicar_formulario(
    formulario_id: int,
    conexao: DepConexao,
    agora: DepAgora,
    entrada: DuplicarEntrada | None = None,
) -> FormularioDetalheSaida:
    nome = entrada.nome if entrada is not None else None
    criado = servico.duplicar_formulario(conexao, formulario_id, nome, agora)
    return _detalhe(criado.formulario, criado.versao)


@roteador.put(
    "/formularios/{formulario_id}/pasta",
    response_model=ResumoDeFormularioSaida,
    tags=["pastas"],
    summary="Move o formulário para uma pasta (ou para a raiz)",
    description=(
        "`pasta_id` nulo leva o formulário à raiz. Só troca a pasta: versões, registros e "
        "referências não mudam. Pasta de destino inexistente é 422 no campo `pasta_id`."
    ),
)
def mover_formulario(
    formulario_id: int, entrada: MoverFormularioEntrada, conexao: DepConexao
) -> ResumoDeFormularioSaida:
    servico.mover_formulario(conexao, formulario_id, entrada.pasta_id)
    detalhe = servico.obter_formulario(conexao, formulario_id)
    return ResumoDeFormularioSaida.do_formulario(detalhe.formulario, detalhe.versao_atual)


@roteador.delete(
    "/formularios/{formulario_id}",
    status_code=204,
    response_class=Response,
    tags=["formulários"],
    summary="Exclui o formulário e suas versões",
    description="409 se outro formulário depende dele ou se ele tem registros.",
    responses=_ERRO_409,
)
def excluir_formulario(formulario_id: int, conexao: DepConexao) -> Response:
    servico.excluir_formulario(conexao, formulario_id)
    return Response(status_code=204)


@roteador.post(
    "/formularios/{formulario_id}/versoes",
    status_code=201,
    response_model=VersaoSaida,
    tags=["versões"],
    summary="Publica a próxima versão",
    description="Versões são imutáveis: não existe `PUT`, `PATCH` nem `DELETE` de versão.",
)
def publicar_versao(
    formulario_id: int, entrada: VersaoEntrada, conexao: DepConexao, agora: DepAgora
) -> VersaoSaida:
    return VersaoSaida.de(servico.publicar_versao(conexao, formulario_id, entrada.definicao, agora))


@roteador.get(
    "/formularios/{formulario_id}/versoes",
    response_model=list[ResumoDeVersaoSaida],
    tags=["versões"],
    summary="Lista as versões, sem a definição",
)
def listar_versoes(formulario_id: int, conexao: DepConexao) -> list[ResumoDeVersaoSaida]:
    return [ResumoDeVersaoSaida.de(v) for v in servico.listar_versoes(conexao, formulario_id)]


@roteador.get(
    "/formularios/{formulario_id}/versoes/{versao_id}",
    response_model=VersaoSaida,
    tags=["versões"],
    summary="Uma versão com a definição (para renderizar um registro antigo)",
)
def obter_versao(formulario_id: int, versao_id: int, conexao: DepConexao) -> VersaoSaida:
    return VersaoSaida.de(servico.obter_versao(conexao, formulario_id, versao_id))


# --- rascunho de versão ---


def _rascunho_saida(conexao: Conexao, rascunho: RascunhoGuardado) -> RascunhoSaida:
    nomes = servico.nomes_de_pessoas(conexao, [rascunho.atualizado_por])
    por = rascunho.atualizado_por
    return RascunhoSaida(
        formulario_id=rascunho.formulario_id,
        definicao=rascunho.definicao,
        base_versao_id=rascunho.base_versao_id,
        revisao=rascunho.revisao,
        atualizado_por=None
        if por is None or por not in nomes
        else PessoaResumoSaida(id=por, nome=nomes[por]),
        atualizado_em=rascunho.atualizado_em,
    )


@roteador.get(
    "/formularios/{formulario_id}/rascunho",
    response_model=RascunhoSaida,
    tags=["rascunho"],
    summary="O rascunho da próxima versão (404 se não há)",
)
def obter_rascunho(formulario_id: int, conexao: DepConexao) -> RascunhoSaida:
    return _rascunho_saida(conexao, servico.obter_rascunho(conexao, formulario_id))


@roteador.put(
    "/formularios/{formulario_id}/rascunho",
    response_model=RascunhoSaida,
    tags=["rascunho"],
    summary="Cria ou substitui o rascunho (aceita definição incompleta)",
    responses={409: {"model": ErroSaida, "description": "Outra pessoa alterou o rascunho."}},
)
def salvar_rascunho(
    formulario_id: int, entrada: RascunhoEntrada, conexao: DepConexao, agora: DepAgora
) -> RascunhoSaida:
    salvo = servico.salvar_rascunho(
        conexao, formulario_id, entrada.definicao, entrada.revisao, agora
    )
    return _rascunho_saida(conexao, salvo)


@roteador.delete(
    "/formularios/{formulario_id}/rascunho",
    status_code=204,
    response_class=Response,
    tags=["rascunho"],
    summary="Descarta o rascunho",
)
def descartar_rascunho(formulario_id: int, conexao: DepConexao) -> Response:
    servico.descartar_rascunho(conexao, formulario_id)
    return Response(status_code=204)


@roteador.post(
    "/formularios/{formulario_id}/rascunho/publicar",
    status_code=201,
    response_model=VersaoSaida,
    tags=["rascunho"],
    summary="Valida o rascunho e publica a versão N+1",
    description="Definição inválida → 422 com os erros e o rascunho continua.",
)
def publicar_rascunho(formulario_id: int, conexao: DepConexao, agora: DepAgora) -> VersaoSaida:
    return VersaoSaida.de(servico.publicar_rascunho(conexao, formulario_id, agora))


# --- pastas ---


@roteador.post(
    "/pastas",
    status_code=201,
    response_model=PastaSaida,
    tags=["pastas"],
    summary="Cria uma pasta (na raiz ou dentro de outra)",
    description=(
        "O nome é único entre pastas irmãs, sem diferenciar maiúsculas/minúsculas nem espaços "
        "nas pontas; repetido é 422 no campo `nome`."
    ),
)
def criar_pasta(entrada: PastaEntrada, conexao: DepConexao, agora: DepAgora) -> PastaSaida:
    return PastaSaida.de(servico.criar_pasta(conexao, entrada.nome, entrada.pasta_pai_id, agora))


@roteador.get(
    "/pastas",
    response_model=list[PastaSaida],
    tags=["pastas"],
    summary="Lista as pastas, em lista plana (o front monta a árvore)",
)
def listar_pastas(conexao: DepConexao) -> list[PastaSaida]:
    return [PastaSaida.de(p) for p in servico.listar_pastas(conexao)]


@roteador.put(
    "/pastas/{pasta_id}",
    response_model=PastaSaida,
    tags=["pastas"],
    summary="Renomeia e/ou move a pasta",
    description=(
        "Substitui `nome` e `pasta_pai_id`. Mover para dentro dela mesma ou de uma subpasta é 422 "
        "no campo `pasta_pai_id`."
    ),
)
def atualizar_pasta(pasta_id: int, entrada: PastaAtualizacao, conexao: DepConexao) -> PastaSaida:
    return PastaSaida.de(
        servico.atualizar_pasta(conexao, pasta_id, entrada.nome, entrada.pasta_pai_id)
    )


@roteador.delete(
    "/pastas/{pasta_id}",
    status_code=204,
    response_class=Response,
    tags=["pastas"],
    summary="Exclui uma pasta vazia",
    description="409 se a pasta tem subpastas ou formulários; nada é apagado em cascata.",
    responses=_ERRO_409,
)
def excluir_pasta(pasta_id: int, conexao: DepConexao) -> Response:
    servico.excluir_pasta(conexao, pasta_id)
    return Response(status_code=204)


# --- definições: validar, prévia, catálogo ---


@roteador.post(
    "/definicoes/validar",
    response_model=ValidarSaida,
    tags=["definições"],
    summary="Valida uma definição sem salvar nada",
    description=(
        "Responde **200** com `{valida, erros}` mesmo quando há erros, porque definição incompleta "
        "é o caso normal enquanto o usuário edita. O 422 vale só ao publicar. "
        "Devolve todos os erros de uma vez."
    ),
)
def validar_definicao(entrada: ValidarEntrada, conexao: DepConexao) -> ValidarSaida:
    resultado = servico.validar_definicao(conexao, entrada.definicao)
    return ValidarSaida(
        valida=resultado.valida, erros=[ErroDeCampoSaida.de(e) for e in resultado.erros]
    )


@roteador.post(
    "/definicoes/previa",
    response_model=PreviaSaida,
    tags=["definições"],
    summary="Calcula os campos calculados sem salvar",
    description=(
        "Usa a mesma função de cálculo do salvar. "
        "Definição inválida devolve os mesmos erros do `validar`."
    ),
)
def previa(entrada: PreviaEntrada, conexao: DepConexao) -> PreviaSaida:
    resultado = servico.previa(conexao, entrada.definicao, entrada.valores)
    return PreviaSaida(
        valida=resultado.valida,
        erros=[ErroDeCampoSaida.de(e) for e in resultado.erros],
        calculados={
            id_do_campo: ResultadoCalculadoSaida.de(r)
            for id_do_campo, r in resultado.calculados.items()
        },
    )


@roteador.get(
    "/catalogo",
    response_model=CatalogoSaida,
    tags=["definições"],
    summary="Tipos de campo, funções de fórmula, `pi` e nomes reservados",
)
def catalogo() -> CatalogoSaida:
    return CatalogoSaida.de(servico.catalogo())


# --- registros ---


@roteador.post(
    "/formularios/{formulario_id}/registros",
    status_code=201,
    response_model=RegistroSaida,
    tags=["registros"],
    summary="Cria um registro numa versão explícita",
)
def criar_registro(
    formulario_id: int, entrada: RegistroEntrada, conexao: DepConexao, agora: DepAgora
) -> RegistroSaida:
    registro = servico.criar_registro(
        conexao, formulario_id, entrada.versao_id, entrada.dados, agora
    )
    return _saida_do_registro(conexao, registro)


@roteador.get(
    "/formularios/{formulario_id}/registros",
    response_model=ListagemDeRegistrosSaida,
    tags=["registros"],
    summary="Lista os registros de uma versão",
    description=(
        "Filtro de igualdade por campo: repita `filtro=campo:valor` (ex.: "
        "`?filtro=resultado:Aprovado&filtro=conforme:true`). Só `selecao`, `sim_nao`, `texto` e "
        "`calculado` booleano; campo fora da definição ou de outro tipo é recusado com 422."
    ),
)
def listar_registros(
    formulario_id: int,
    conexao: DepConexao,
    versao_id: int | None = None,
    limite: Annotated[int, Query(ge=1, le=servico.LIMITE_MAXIMO)] = 50,
    deslocamento: Annotated[int, Query(ge=0)] = 0,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    meus: Annotated[bool, Query(description="Só os registros que eu criei.")] = False,
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> ListagemDeRegistrosSaida:
    listagem = servico.listar_registros(
        conexao,
        formulario_id,
        versao_id=versao_id,
        filtros=ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
        limite=limite,
        deslocamento=deslocamento,
        meus=meus,
    )
    nomes = servico.nomes_de_pessoas(
        conexao, [i for r in listagem.itens for i in (r.criado_por, r.atualizado_por)]
    )
    return ListagemDeRegistrosSaida(
        versao_id=listagem.versao_id,
        colunas=[coluna_de(c) for c in listagem.colunas],
        itens=[
            RegistroSaida.de(r, nomes, servico.estado_do_registro(r.dados, listagem.campo_status))
            for r in listagem.itens
        ],
        total=listagem.total,
        exibicao=ExibicaoSaida(
            destaque=listagem.exibicao.destaque,
            status=listagem.exibicao.status,
            resumo=list(listagem.exibicao.resumo),
        ),
    )


@roteador.get(
    "/formularios/{formulario_id}/registros/contagens",
    response_model=ContagensSaida,
    tags=["registros"],
    summary="Registros por estado (conforme, não conforme, erro, aguardando)",
    description="Mesma versão e mesmos filtros da listagem; o estado é decidido pelo servidor.",
)
def contar_registros(
    formulario_id: int,
    conexao: DepConexao,
    versao_id: int | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    meus: bool = False,
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> ContagensSaida:
    contagens = servico.contar_por_estado(
        conexao,
        formulario_id,
        versao_id=versao_id,
        filtros=ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
        meus=meus,
    )
    return ContagensSaida(**dataclasses.asdict(contagens))


@roteador.get(
    "/formularios/{formulario_id}/registros/exportar",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV para o Excel em português."}},
    tags=["registros"],
    summary="Exporta os registros em CSV",
    description=(
        "Mesma versão e mesmos filtros da listagem. UTF-8 com BOM, separador `;`, vírgula decimal, "
        "cabeçalho `rótulo (unidade)`."
    ),
)
def exportar_registros(
    formulario_id: int,
    conexao: DepConexao,
    versao_id: int | None = None,
    criado_de: date | None = None,
    criado_ate: date | None = None,
    meus: bool = False,
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> Response:
    nome = servico.obter_formulario(conexao, formulario_id).formulario.nome
    conteudo = servico.exportar_csv(
        conexao,
        formulario_id,
        versao_id=versao_id,
        filtros=ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
        meus=meus,
    )
    return Response(
        content=conteudo,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_nome_de_arquivo(nome)}.csv"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@roteador.get(
    "/registros/{registro_id}",
    response_model=RegistroSaida,
    tags=["registros"],
    summary="Um registro; o `versao_id` dele aponta a definição certa",
)
def obter_registro(registro_id: int, conexao: DepConexao) -> RegistroSaida:
    return _saida_do_registro(conexao, servico.obter_registro(conexao, registro_id))


@roteador.put(
    "/registros/{registro_id}",
    response_model=RegistroSaida,
    tags=["registros"],
    summary="Substitui todos os valores (sem PATCH)",
    description=(
        "Valida e recalcula tudo; o registro continua na versão de origem "
        "e os dependentes são recalculados."
    ),
)
def atualizar_registro(
    registro_id: int,
    entrada: RegistroAtualizacao,
    conexao: DepConexao,
    agora: DepAgora,
) -> RegistroSaida:
    registro = servico.atualizar_registro(
        conexao, registro_id, entrada.dados, agora, entrada.revisao
    )
    return _saida_do_registro(conexao, registro)


@roteador.delete(
    "/registros/{registro_id}",
    status_code=204,
    response_class=Response,
    tags=["registros"],
    summary="Exclui o registro de verdade",
    description="409 se outro registro o referencia.",
    responses=_ERRO_409,
)
def excluir_registro(registro_id: int, conexao: DepConexao, agora: DepAgora) -> Response:
    servico.excluir_registro(conexao, registro_id, agora)
    return Response(status_code=204)


@roteador.get(
    "/registros/{registro_id}/historico",
    response_model=list[HistoricoSaida],
    tags=["registros"],
    summary="Histórico de alterações do registro (quem, quando, o que havia antes)",
)
def historico_do_registro(registro_id: int, conexao: DepConexao) -> list[HistoricoSaida]:
    return [
        HistoricoSaida(
            id=e.id,
            usuario_id=e.usuario_id,
            pessoa=nome,
            quando=e.quando,
            acao=e.acao,
            valores_anteriores=e.valores_anteriores,
            motivo=e.motivo,
        )
        for e, nome in servico.historico_do_registro(conexao, registro_id)
    ]


# --- apoio ---


def _saida_do_registro(conexao: Conexao, registro: Registro) -> RegistroSaida:
    nomes = servico.nomes_de_pessoas(conexao, [registro.criado_por, registro.atualizado_por])
    return RegistroSaida.de(registro, nomes)


def _detalhe(formulario: Formulario, versao: Versao) -> FormularioDetalheSaida:
    return FormularioDetalheSaida(
        id=formulario.id,
        nome=formulario.nome,
        criado_em=formulario.criado_em,
        versao_atual=VersaoSaida.de(versao),
        pasta_id=formulario.pasta_id,
    )


def ler_filtros(filtros: list[str]) -> dict[str, str]:
    lidos = {}
    erros = []
    for filtro in filtros:
        campo, separador, valor = filtro.partition(":")
        if not separador or not campo:
            erros.append(
                ErroDeCampo("filtro", f"O filtro '{filtro}' deve ter o formato campo:valor.")
            )
        else:
            lidos[campo] = valor
    if erros:
        raise RegistroInvalido(tuple(erros))
    return lidos


def _nome_de_arquivo(nome: str) -> str:
    """Nome seguro para o `Content-Disposition`: só ASCII simples, sem aspas nem barras."""
    limpo = re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_")
    return limpo or "registros"
