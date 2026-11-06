"""Endpoints de pessoa, equipe, cargos, convites e termos (AGENTS.md §2.12 a §2.15).

Só traduz HTTP: a regra (administrador que não some, ninguém concede o que não tem, convite de
uso único) está em `servicos/equipes.py`. A permissão de cada rota vem da matriz única
(`api/matriz_permissoes.py`), aplicada pela dependência `autorizar`.
"""

from fastapi import APIRouter, Depends, Response

from forms.api.dependencias import DepAgora, DepConexao, autorizar
from forms.api.esquemas import (
    AceitarConviteSaida,
    CargoEntrada,
    CargoResumoSaida,
    CargoSaida,
    CatalogoDePermissoesSaida,
    ConsentimentoEntrada,
    ConsentimentoSaida,
    ConsentimentosSaida,
    ConviteCriadoSaida,
    ConviteEntrada,
    ConviteSaida,
    DocumentoLegalSaida,
    DocumentosLegaisSaida,
    EquipeDaPessoaSaida,
    EquipeEntrada,
    EquipeSaida,
    ErroSaida,
    EuSaida,
    GuiaSaida,
    GuiasSaida,
    MembroSaida,
    PermissaoSaida,
    PessoaSaida,
    SaudeSaida,
    TrocarCargoEntrada,
)
from forms.dominio.permissoes import PERMISSOES
from forms.infra import ajuda, legal
from forms.repositorios.equipes import Cargo, Convite, Membro
from forms.servicos import equipes as servico_equipes

_ERROS = {
    401: {"model": ErroSaida, "description": "Sem token, token inválido ou expirado."},
    403: {"model": ErroSaida, "description": "Sem permissão, sem equipe ou termos pendentes."},
    404: {"model": ErroSaida, "description": "Recurso inexistente."},
    422: {"model": ErroSaida, "description": "Dados inválidos, com os erros por campo."},
}

roteador_publico = APIRouter(tags=["público"])
roteador = APIRouter(dependencies=[Depends(autorizar)], responses=_ERROS)


# --- público ---


@roteador_publico.get("/healthz", response_model=SaudeSaida, summary="O processo está vivo")
def saude() -> SaudeSaida:
    return SaudeSaida(status="ok")


@roteador_publico.get(
    "/legal", response_model=DocumentosLegaisSaida, summary="Termos de Uso e Política vigentes"
)
def documentos_legais() -> DocumentosLegaisSaida:
    return DocumentosLegaisSaida(documentos=[_documento(legal.ler(d)) for d in legal.DOCUMENTOS])


@roteador_publico.get(
    "/legal/{documento}",
    response_model=DocumentoLegalSaida,
    summary="Um documento legal na versão vigente",
    responses={404: {"model": ErroSaida, "description": "Documento inexistente."}},
)
def documento_legal(documento: str) -> DocumentoLegalSaida:
    return _documento(legal.ler(documento))


@roteador_publico.get(
    "/catalogo/permissoes",
    response_model=CatalogoDePermissoesSaida,
    summary="As permissões que um cargo pode ter",
)
def catalogo_de_permissoes() -> CatalogoDePermissoesSaida:
    return CatalogoDePermissoesSaida(
        permissoes=[
            PermissaoSaida(id=p.id, grupo=p.grupo, rotulo=p.rotulo, descricao=p.descricao)
            for p in PERMISSOES
        ]
    )


def _documento(doc: legal.Documento) -> DocumentoLegalSaida:
    return DocumentoLegalSaida(
        id=doc.id, titulo=doc.titulo, versao=doc.versao, markdown=doc.markdown
    )


@roteador_publico.get(
    "/ajuda",
    response_model=GuiasSaida,
    summary="Os guias da central de ajuda",
)
def guias_de_ajuda() -> GuiasSaida:
    return GuiasSaida(
        guias=[GuiaSaida(id=g.id, titulo=g.titulo, markdown=g.markdown) for g in ajuda.listar()]
    )


@roteador_publico.get(
    "/ajuda/{guia}",
    response_model=GuiaSaida,
    summary="Um guia da central de ajuda",
    responses={404: {"model": ErroSaida, "description": "Guia inexistente."}},
)
def guia_de_ajuda(guia: str) -> GuiaSaida:
    g = ajuda.ler(guia)
    return GuiaSaida(id=g.id, titulo=g.titulo, markdown=g.markdown)


# --- eu ---


@roteador.get("/eu", response_model=EuSaida, tags=["pessoa"], summary="Quem sou eu")
def quem_sou_eu(conexao: DepConexao) -> EuSaida:
    usuario_id = conexao.usuario_id
    assert usuario_id is not None  # a dependência `autorizar` identifica a pessoa
    pessoa = servico_equipes.obter_pessoa(conexao, usuario_id)
    equipes = []
    for equipe in servico_equipes.minhas_equipes(conexao, usuario_id):
        cargo, permissoes = servico_equipes.cargo_e_permissoes(conexao, equipe.cargo_id, equipe.id)
        equipes.append(
            EquipeDaPessoaSaida(
                id=equipe.id,
                nome=equipe.nome,
                ativa=equipe.ativa,
                cargo=CargoResumoSaida(id=equipe.cargo_id, nome=cargo),
                permissoes=sorted(permissoes),
            )
        )
    return EuSaida(
        pessoa=PessoaSaida(id=pessoa.id, nome=pessoa.nome, email=pessoa.email),
        equipes=equipes,
        termos_pendentes=list(servico_equipes.termos_pendentes(conexao, usuario_id)),
    )


@roteador.get(
    "/consentimentos",
    response_model=ConsentimentosSaida,
    tags=["pessoa"],
    summary="Meus aceites dos Termos e da Política",
)
def consentimentos(conexao: DepConexao) -> ConsentimentosSaida:
    usuario_id = _pessoa(conexao)
    return ConsentimentosSaida(
        aceites=[
            ConsentimentoSaida(documento=d, versao=v, aceito_em=quando)
            for d, v, quando in servico_equipes.meus_consentimentos(conexao, usuario_id)
        ],
        pendentes=list(servico_equipes.termos_pendentes(conexao, usuario_id)),
    )


@roteador.post(
    "/consentimentos",
    response_model=ConsentimentosSaida,
    status_code=201,
    tags=["pessoa"],
    summary="Aceito a versão vigente dos Termos e da Política",
)
def aceitar_termos(
    entrada: ConsentimentoEntrada, conexao: DepConexao, agora: DepAgora
) -> ConsentimentosSaida:
    usuario_id = _pessoa(conexao)
    documentos = None if entrada.documentos is None else tuple(entrada.documentos)
    servico_equipes.aceitar_termos(conexao, usuario_id, agora, documentos)
    return consentimentos(conexao)


@roteador.post(
    "/convites/{token}/aceitar",
    response_model=AceitarConviteSaida,
    tags=["convites"],
    summary="Aceito um convite e entro na equipe",
)
def aceitar_convite(token: str, conexao: DepConexao, agora: DepAgora) -> AceitarConviteSaida:
    grupo = servico_equipes.aceitar_convite(conexao, token, _pessoa(conexao), agora)
    return AceitarConviteSaida(equipe=EquipeSaida(id=grupo.id, nome=grupo.nome))


def _pessoa(conexao: DepConexao) -> int:
    usuario_id = conexao.usuario_id
    assert usuario_id is not None  # a dependência `autorizar` identifica a pessoa
    return usuario_id


# --- equipe ---


@roteador.get("/equipe", response_model=EquipeSaida, tags=["equipe"], summary="A equipe ativa")
def equipe_ativa(conexao: DepConexao) -> EquipeSaida:
    grupo = servico_equipes.obter_equipe(conexao)
    return EquipeSaida(id=grupo.id, nome=grupo.nome)


@roteador.put("/equipe", response_model=EquipeSaida, tags=["equipe"], summary="Renomeia a equipe")
def renomear_equipe(entrada: EquipeEntrada, conexao: DepConexao) -> EquipeSaida:
    servico_equipes.renomear_equipe(conexao, entrada.nome)
    return equipe_ativa(conexao)


@roteador.post(
    "/equipe/sair",
    status_code=204,
    response_class=Response,
    tags=["equipe"],
    summary="Saio da equipe",
)
def sair_da_equipe(conexao: DepConexao) -> Response:
    servico_equipes.sair_da_equipe(conexao)
    return Response(status_code=204)


# --- cargos ---


def _cargo(cargo: Cargo) -> CargoSaida:
    return CargoSaida(
        id=cargo.id,
        nome=cargo.nome,
        descricao=cargo.descricao,
        padrao=cargo.padrao,
        permissoes=list(cargo.permissoes),
        pessoas=cargo.pessoas,
    )


@roteador.get(
    "/cargos", response_model=list[CargoSaida], tags=["cargos"], summary="Os cargos da equipe"
)
def listar_cargos(conexao: DepConexao) -> list[CargoSaida]:
    return [_cargo(c) for c in servico_equipes.listar_cargos(conexao)]


@roteador.post(
    "/cargos", response_model=CargoSaida, status_code=201, tags=["cargos"], summary="Cria um cargo"
)
def criar_cargo(entrada: CargoEntrada, conexao: DepConexao) -> CargoSaida:
    return _cargo(
        servico_equipes.criar_cargo(conexao, entrada.nome, entrada.descricao, entrada.permissoes)
    )


@roteador.put(
    "/cargos/{cargo_id}",
    response_model=CargoSaida,
    tags=["cargos"],
    summary="Substitui nome, descrição e permissões do cargo",
)
def atualizar_cargo(cargo_id: int, entrada: CargoEntrada, conexao: DepConexao) -> CargoSaida:
    return _cargo(
        servico_equipes.atualizar_cargo(
            conexao, cargo_id, entrada.nome, entrada.descricao, entrada.permissoes
        )
    )


@roteador.delete(
    "/cargos/{cargo_id}",
    status_code=204,
    response_class=Response,
    tags=["cargos"],
    summary="Exclui o cargo (só sem pessoas)",
)
def excluir_cargo(cargo_id: int, conexao: DepConexao) -> Response:
    servico_equipes.excluir_cargo(conexao, cargo_id)
    return Response(status_code=204)


# --- membros ---


def _membro(membro: Membro) -> MembroSaida:
    return MembroSaida(
        usuario_id=membro.usuario_id,
        nome=membro.nome,
        email=membro.email,
        cargo=CargoResumoSaida(id=membro.cargo_id, nome=membro.cargo_nome),
        ativo=membro.ativo,
        entrou_em=membro.entrou_em,
    )


@roteador.get(
    "/membros", response_model=list[MembroSaida], tags=["equipe"], summary="As pessoas da equipe"
)
def listar_membros(conexao: DepConexao) -> list[MembroSaida]:
    return [_membro(m) for m in servico_equipes.listar_membros(conexao)]


@roteador.put(
    "/membros/{usuario_id}/cargo",
    status_code=204,
    response_class=Response,
    tags=["equipe"],
    summary="Muda o cargo de uma pessoa",
)
def mudar_cargo(usuario_id: int, entrada: TrocarCargoEntrada, conexao: DepConexao) -> Response:
    servico_equipes.mudar_cargo(conexao, usuario_id, entrada.cargo_id)
    return Response(status_code=204)


@roteador.post(
    "/membros/{usuario_id}/desativar",
    status_code=204,
    response_class=Response,
    tags=["equipe"],
    summary="Desativa a pessoa (perde o acesso na hora; os registros ficam)",
)
def desativar(usuario_id: int, conexao: DepConexao) -> Response:
    servico_equipes.desativar_pessoa(conexao, usuario_id)
    return Response(status_code=204)


@roteador.post(
    "/membros/{usuario_id}/reativar",
    status_code=204,
    response_class=Response,
    tags=["equipe"],
    summary="Reativa a pessoa",
)
def reativar(usuario_id: int, conexao: DepConexao) -> Response:
    servico_equipes.reativar_pessoa(conexao, usuario_id)
    return Response(status_code=204)


# --- convites ---


def _convite(convite: Convite) -> ConviteSaida:
    return ConviteSaida(
        id=convite.id,
        email=convite.email,
        cargo=CargoResumoSaida(id=convite.cargo_id, nome=convite.cargo_nome),
        criado_em=convite.criado_em,
        expira_em=convite.expira_em,
    )


@roteador.get(
    "/convites", response_model=list[ConviteSaida], tags=["convites"], summary="Convites pendentes"
)
def listar_convites(conexao: DepConexao) -> list[ConviteSaida]:
    return [_convite(c) for c in servico_equipes.listar_convites(conexao)]


@roteador.post(
    "/convites",
    response_model=ConviteCriadoSaida,
    status_code=201,
    tags=["convites"],
    summary="Cria um convite (o token só aparece nesta resposta)",
)
def criar_convite(
    entrada: ConviteEntrada, conexao: DepConexao, agora: DepAgora
) -> ConviteCriadoSaida:
    convite_id, token = servico_equipes.criar_convite(
        conexao, entrada.email, entrada.cargo_id, agora
    )
    convite = next(c for c in servico_equipes.listar_convites(conexao) if c.id == convite_id)
    return ConviteCriadoSaida(convite=_convite(convite), token=token)


@roteador.delete(
    "/convites/{convite_id}",
    status_code=204,
    response_class=Response,
    tags=["convites"],
    summary="Revoga um convite pendente",
)
def revogar_convite(convite_id: int, conexao: DepConexao, agora: DepAgora) -> Response:
    servico_equipes.revogar_convite(conexao, convite_id, agora)
    return Response(status_code=204)
