"""Endpoints da API (AGENTS.md §2.2, §2.3, §2.8). Só traduz HTTP: nenhuma regra de negócio.

Cada rota chama uma função de `servico` e converte o resultado em modelo de resposta. As exceções
de domínio viram o status HTTP certo em `api.py`.
"""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.security import APIKeyHeader

from forms import fotos, servico
from forms.api_esquemas import (
    AnexoSaida,
    CatalogoSaida,
    ErroDeCampoSaida,
    ErroSaida,
    FormularioDetalheSaida,
    FormularioEntrada,
    ListagemDeRegistrosSaida,
    LoteEntrada,
    PreviaEntrada,
    PreviaSaida,
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
from forms.models import ErroDeCampo, Formulario, RegistroInvalido, Versao
from forms.servico import Conexao, Rascunho

CABECALHO_DO_TOKEN = "X-Forms-Token"

# O token é conferido pelo middleware; este esquema só o descreve no OpenAPI (botão "Authorize").
esquema_do_token = APIKeyHeader(
    name=CABECALHO_DO_TOKEN, auto_error=False, scheme_name="TokenDaExecucao"
)

# Erros comuns a (quase) todo endpoint, para o OpenAPI mostrar o formato uniforme.
_ERROS = {
    401: {"model": ErroSaida, "description": "Token ausente ou inválido."},
    404: {"model": ErroSaida, "description": "Recurso inexistente."},
    422: {"model": ErroSaida, "description": "Dados inválidos, com os erros por campo."},
}
_ERRO_409 = {409: {"model": ErroSaida, "description": "Exclusão bloqueada por vínculo."}}

roteador = APIRouter(dependencies=[Depends(esquema_do_token)], responses=_ERROS)


# --- dependências (injetadas por parâmetro, nunca globais) ---


def obter_conexao(request: Request) -> Iterator[Conexao]:
    conexao = servico.abrir_banco(request.app.state.configuracao.banco)
    try:
        yield conexao
    finally:
        conexao.close()


def obter_agora() -> datetime:
    return datetime.now(UTC)


def obter_pasta_de_dados(request: Request) -> Path:
    return request.app.state.configuracao.pasta_de_dados


DepConexao = Annotated[Conexao, Depends(obter_conexao)]
DepAgora = Annotated[datetime, Depends(obter_agora)]
DepPasta = Annotated[Path, Depends(obter_pasta_de_dados)]


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
    criado = servico.criar_formulario(conexao, entrada.nome, entrada.definicao, agora)
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
    return RegistroSaida.de(registro)


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
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> ListagemDeRegistrosSaida:
    listagem = servico.listar_registros(
        conexao,
        formulario_id,
        versao_id=versao_id,
        filtros=_ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
        limite=limite,
        deslocamento=deslocamento,
    )
    return ListagemDeRegistrosSaida(
        versao_id=listagem.versao_id,
        colunas=[coluna_de(c) for c in listagem.colunas],
        itens=[RegistroSaida.de(r) for r in listagem.itens],
        total=listagem.total,
    )


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
    filtro: Annotated[list[str] | None, Query(description="`campo:valor`, repetível.")] = None,
) -> Response:
    nome = servico.obter_formulario(conexao, formulario_id).formulario.nome
    conteudo = servico.exportar_csv(
        conexao,
        formulario_id,
        versao_id=versao_id,
        filtros=_ler_filtros(filtro or []),
        criado_de=criado_de,
        criado_ate=criado_ate,
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
    return RegistroSaida.de(servico.obter_registro(conexao, registro_id))


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
    pasta: DepPasta,
) -> RegistroSaida:
    return RegistroSaida.de(
        servico.atualizar_registro(conexao, registro_id, entrada.dados, agora, pasta)
    )


@roteador.delete(
    "/registros/{registro_id}",
    status_code=204,
    response_class=Response,
    tags=["registros"],
    summary="Exclui o registro de verdade",
    description="409 se outro registro o referencia.",
    responses=_ERRO_409,
)
def excluir_registro(registro_id: int, conexao: DepConexao, pasta: DepPasta) -> Response:
    servico.excluir_registro(conexao, registro_id, pasta)
    return Response(status_code=204)


# --- anexos (fotos) ---


@roteador.post(
    "/anexos",
    status_code=201,
    response_model=AnexoSaida,
    tags=["anexos"],
    summary="Envia uma foto (multipart, campo `arquivo`)",
    description=(
        "JPEG, PNG ou WebP até 20 MB; vira WebP sem metadados. O registro guarda a lista de `id`s. "
        "O nome do arquivo enviado nunca é usado."
    ),
)
def enviar_anexo(
    conexao: DepConexao,
    agora: DepAgora,
    pasta: DepPasta,
    arquivo: Annotated[UploadFile, File(description="A imagem.")],
) -> AnexoSaida:
    # Lê um byte além do limite: basta para `fotos` recusar sem carregar um arquivo gigante.
    conteudo = arquivo.file.read(fotos.TAMANHO_MAXIMO_ENTRADA + 1)
    anexo = servico.guardar_anexo(conexao, pasta, conteudo, agora)
    return AnexoSaida(
        id=anexo.id, largura=anexo.largura, altura=anexo.altura, tamanho_bytes=anexo.tamanho_bytes
    )


@roteador.get(
    "/anexos/{anexo_id}",
    response_class=Response,
    responses={200: {"content": {"image/webp": {}}, "description": "A foto em WebP."}},
    tags=["anexos"],
    summary="A foto em WebP",
)
def obter_anexo(anexo_id: int, conexao: DepConexao, pasta: DepPasta) -> Response:
    return Response(
        content=servico.ler_anexo(conexao, pasta, anexo_id),
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- apoio ---


def _detalhe(formulario: Formulario, versao: Versao) -> FormularioDetalheSaida:
    return FormularioDetalheSaida(
        id=formulario.id,
        nome=formulario.nome,
        criado_em=formulario.criado_em,
        versao_atual=VersaoSaida.de(versao),
    )


def _ler_filtros(filtros: list[str]) -> dict[str, str]:
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
