"""Casos de uso de pessoas, equipes, cargos, convites e consentimentos (AGENTS.md §2.12–§2.15).

Regras que valem aqui, e não na API: sempre existe ao menos uma pessoa ativa que edita cargos;
ninguém concede o que não tem (convite, cargo ou permissão acima do próprio); o token do convite
só existe em claro uma vez. O `servico` não sabe de HTTP: o contexto vem pela conexão.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from forms import legal, repositorio_equipes, segredos
from forms.banco import Conexao
from forms.models import (
    CargoInvalido,
    Contexto,
    ErroDeCampo,
    ErroDeDominio,
    NaoEncontrado,
    SemAcessoAEquipe,
    SemPermissao,
    TermosPendentes,
    ValorInvalido,
)
from forms.permissoes import CARGOS_PADRAO, IDS_DE_PERMISSAO, NOME_DO_ADMINISTRADOR
from forms.repositorio_equipes import Cargo, Convite, Grupo, Membro, Usuario
from forms.servico_base import transacao

PERMISSAO_DE_ADMINISTRACAO = "cargos:editar"
VALIDADE_DO_CONVITE = timedelta(days=7)
INTERVALO_DO_ACESSO = timedelta(minutes=5)


@dataclass(frozen=True)
class EquipeDaPessoa:
    id: int
    nome: str
    cargo_id: int
    ativa: bool


# --- equipes ---


def criar_equipe(conexao: Conexao, nome: str, agora: datetime) -> tuple[Grupo, Cargo]:
    """Cria a equipe com os cargos de partida; devolve o cargo Administrador (§2.13)."""
    nome = nome.strip()
    if not nome:
        raise ValorInvalido("O nome da equipe é obrigatório.")
    with transacao(conexao):
        grupo = repositorio_equipes.criar_grupo(conexao, nome, agora)
        # O RLS dos cargos exige a equipe declarada na conexão antes de inserir.
        anterior = conexao.contexto
        conexao.definir_contexto(Contexto(grupo.id, anterior.usuario_id if anterior else None))
        try:
            administrador = None
            for padrao in CARGOS_PADRAO:
                cargo = repositorio_equipes.criar_cargo(
                    conexao, grupo.id, padrao.nome, padrao.descricao, padrao.permissoes, padrao=True
                )
                if padrao.nome == NOME_DO_ADMINISTRADOR:
                    administrador = cargo
        finally:
            conexao.definir_contexto(anterior)
    assert administrador is not None
    return grupo, administrador


def obter_equipe(conexao: Conexao) -> Grupo:
    return repositorio_equipes.obter_grupo(conexao, conexao.grupo_id)


def obter_pessoa(conexao: Conexao, usuario_id: int) -> Usuario:
    return repositorio_equipes.obter_usuario(conexao, usuario_id)


@contextmanager
def declarar_equipe(conexao: Conexao, grupo_id: int) -> Iterator[None]:
    """Declara a equipe na conexão só durante a leitura de um cargo.

    `cargos` tem Row Level Security: sem a equipe declarada, o papel do aplicativo não enxerga o
    cargo de ninguém. A equipe aqui é uma candidata (vem do cabeçalho ou da lista de equipes da
    própria pessoa): quem confere a pertença é `membros_grupo`, que não tem RLS.
    """
    anterior = conexao.contexto
    conexao.definir_contexto(Contexto(grupo_id, anterior.usuario_id if anterior else None))
    try:
        yield
    finally:
        conexao.definir_contexto(anterior)


def cargo_e_permissoes(
    conexao: Conexao, cargo_id: int, grupo_id: int
) -> tuple[str, frozenset[str]]:
    """Nome e permissões de um cargo (para o `GET /eu`)."""
    with declarar_equipe(conexao, grupo_id):
        linha = conexao.execute("SELECT nome FROM cargos WHERE id = %s", (cargo_id,)).fetchone()
    nome = str(linha["nome"]) if linha else ""
    return nome, repositorio_equipes.permissoes_do_cargo(conexao, cargo_id)


def minhas_equipes(conexao: Conexao, usuario_id: int) -> list[EquipeDaPessoa]:
    return [
        EquipeDaPessoa(grupo.id, grupo.nome, cargo_id, ativo)
        for grupo, cargo_id, ativo in repositorio_equipes.grupos_do_usuario(conexao, usuario_id)
    ]


def renomear_equipe(conexao: Conexao, nome: str) -> None:
    nome = nome.strip()
    if not nome:
        raise ValorInvalido("O nome da equipe é obrigatório.")
    repositorio_equipes.renomear_grupo(conexao, conexao.grupo_id, nome)


# --- pessoas e contexto ---


def identificar(
    conexao: Conexao,
    sub: str,
    nome: str | None,
    email: str | None,
    agora: datetime,
    perfil: Callable[[str], tuple[str | None, str | None]] | None = None,
) -> Usuario:
    """Primeira vez que a pessoa aparece com um token válido: cria o registro dela (JIT).

    O token de acesso não traz nome nem e-mail; `perfil` (o Logto) os busca só nessa primeira vez.
    Se o Logto não responder, a pessoa entra com um nome genérico e o perfil vem na próxima.
    """
    usuario = repositorio_equipes.obter_usuario_por_sub(conexao, sub)
    if usuario is None:
        if perfil is not None and not (nome and email):
            try:
                nome_do_logto, email_do_logto = perfil(sub)
            except ErroDeDominio:
                nome_do_logto = email_do_logto = None
            nome, email = nome or nome_do_logto, email or email_do_logto
        return repositorio_equipes.criar_usuario(
            conexao, sub, nome or "Pessoa sem nome", email, agora
        )
    visto = usuario.ultimo_acesso_em
    mudou = (nome and nome != usuario.nome) or (email and email != usuario.email)
    # Uma escrita por requisição seria desperdício: o último acesso só é regravado de 5 em 5 min.
    if mudou or visto is None or datetime.fromisoformat(visto) < agora - INTERVALO_DO_ACESSO:
        repositorio_equipes.registrar_acesso(conexao, usuario.id, agora, nome, email)
        return repositorio_equipes.obter_usuario(conexao, usuario.id)
    return usuario


def contexto_da_pessoa(conexao: Conexao, usuario_id: int, grupo_id: int) -> Contexto:
    """Equipe ativa da requisição, conferida no banco: o cabeçalho do cliente não basta (§2.13).

    O cargo e as permissões são lidos **a cada requisição**, então mudar o cargo ou desativar
    alguém vale na hora.
    """
    with declarar_equipe(conexao, grupo_id):
        membro = repositorio_equipes.obter_membro(conexao, grupo_id, usuario_id)
    if membro is None or not membro.ativo:
        raise SemAcessoAEquipe("Você não faz parte desta equipe ou seu acesso foi desativado.")
    permissoes = repositorio_equipes.permissoes_do_cargo(conexao, membro.cargo_id)
    return Contexto(grupo_id, usuario_id, permissoes)


def exigir(conexao: Conexao, permissao: str) -> None:
    contexto = conexao.contexto
    if contexto is None or not contexto.tem(permissao):
        raise SemPermissao(permissao)


# --- cargos ---


def listar_cargos(conexao: Conexao) -> list[Cargo]:
    return repositorio_equipes.listar_cargos(conexao, conexao.grupo_id)


def criar_cargo(conexao: Conexao, nome: str, descricao: str, permissoes: list[str]) -> Cargo:
    _validar_cargo(conexao, nome, permissoes)
    return repositorio_equipes.criar_cargo(conexao, conexao.grupo_id, nome, descricao, permissoes)


def atualizar_cargo(
    conexao: Conexao, cargo_id: int, nome: str, descricao: str, permissoes: list[str]
) -> Cargo:
    grupo_id = conexao.grupo_id
    atual = repositorio_equipes.obter_cargo(conexao, grupo_id, cargo_id)
    _validar_cargo(conexao, nome, permissoes)
    with transacao(conexao):
        # Trava as pessoas da equipe: duas edições simultâneas não esvaziam a administração.
        conexao.execute("SELECT 1 FROM membros_grupo WHERE grupo_id = %s FOR UPDATE", (grupo_id,))
        novo = repositorio_equipes.atualizar_cargo(
            conexao, grupo_id, cargo_id, nome, descricao, permissoes
        )
        if (
            PERMISSAO_DE_ADMINISTRACAO in atual.permissoes
            and not repositorio_equipes.contar_pessoas_com_permissao(
                conexao, grupo_id, PERMISSAO_DE_ADMINISTRACAO
            )
        ):
            raise CargoInvalido(
                (
                    ErroDeCampo(
                        "permissoes",
                        "A equipe precisa ter ao menos uma pessoa ativa que edite cargos.",
                    ),
                )
            )
    return novo


def excluir_cargo(conexao: Conexao, cargo_id: int) -> None:
    grupo_id = conexao.grupo_id
    cargo = repositorio_equipes.obter_cargo(conexao, grupo_id, cargo_id)
    if repositorio_equipes.contar_membros_do_cargo(conexao, cargo_id):
        raise CargoInvalido(
            (ErroDeCampo("cargo", "Há pessoas com este cargo; mude o cargo delas antes."),)
        )
    with transacao(conexao):
        repositorio_equipes.excluir_cargo(conexao, grupo_id, cargo.id)


def _validar_cargo(conexao: Conexao, nome: str, permissoes: list[str]) -> None:
    erros = []
    if not nome.strip():
        erros.append(ErroDeCampo("nome", "O nome do cargo é obrigatório."))
    desconhecidas = sorted(set(permissoes) - IDS_DE_PERMISSAO)
    if desconhecidas:
        erros.append(ErroDeCampo("permissoes", f"Permissão inexistente: {desconhecidas[0]}."))
    # Ninguém concede o que não tem: impede subir o próprio nível por um cargo novo.
    contexto = conexao.contexto
    excesso = sorted(set(permissoes) - (contexto.permissoes if contexto else frozenset()))
    if excesso and not erros:
        erros.append(ErroDeCampo("permissoes", f"Você não pode conceder a permissão {excesso[0]}."))
    if erros:
        raise CargoInvalido(tuple(erros))


# --- membros ---


def listar_membros(conexao: Conexao) -> list[Membro]:
    return repositorio_equipes.listar_membros(conexao, conexao.grupo_id)


def mudar_cargo(conexao: Conexao, usuario_id: int, cargo_id: int) -> None:
    grupo_id = conexao.grupo_id
    cargo = repositorio_equipes.obter_cargo(conexao, grupo_id, cargo_id)
    _nao_conceder_alem_do_proprio(conexao, cargo)
    with transacao(conexao):
        conexao.execute("SELECT 1 FROM membros_grupo WHERE grupo_id = %s FOR UPDATE", (grupo_id,))
        repositorio_equipes.trocar_cargo_do_membro(conexao, grupo_id, usuario_id, cargo_id)
        _garantir_administracao(conexao, grupo_id)


def desativar_pessoa(conexao: Conexao, usuario_id: int) -> None:
    grupo_id = conexao.grupo_id
    with transacao(conexao):
        conexao.execute("SELECT 1 FROM membros_grupo WHERE grupo_id = %s FOR UPDATE", (grupo_id,))
        repositorio_equipes.definir_membro_ativo(conexao, grupo_id, usuario_id, False)
        _garantir_administracao(conexao, grupo_id)


def reativar_pessoa(conexao: Conexao, usuario_id: int) -> None:
    repositorio_equipes.definir_membro_ativo(conexao, conexao.grupo_id, usuario_id, True)


def sair_da_equipe(conexao: Conexao) -> None:
    """A própria pessoa sai; a equipe nunca fica sem quem edite cargos."""
    usuario_id = conexao.usuario_id
    if usuario_id is None:
        raise SemAcessoAEquipe("Pessoa não identificada.")
    grupo_id = conexao.grupo_id
    with transacao(conexao):
        conexao.execute("SELECT 1 FROM membros_grupo WHERE grupo_id = %s FOR UPDATE", (grupo_id,))
        repositorio_equipes.remover_membro(conexao, grupo_id, usuario_id)
        _garantir_administracao(conexao, grupo_id)


def _garantir_administracao(conexao: Conexao, grupo_id: int) -> None:
    if not repositorio_equipes.contar_pessoas_com_permissao(
        conexao, grupo_id, PERMISSAO_DE_ADMINISTRACAO
    ):
        raise CargoInvalido(
            (
                ErroDeCampo(
                    "cargo",
                    "A equipe precisa ter ao menos uma pessoa ativa que edite cargos "
                    "(um administrador).",
                ),
            )
        )


def _nao_conceder_alem_do_proprio(conexao: Conexao, cargo: Cargo) -> None:
    contexto = conexao.contexto
    meu = contexto.permissoes if contexto else frozenset()
    if not set(cargo.permissoes) <= meu:
        raise SemPermissao("equipe:atribuir_cargos")


# --- convites ---


def criar_convite(conexao: Conexao, email: str, cargo_id: int, agora: datetime) -> tuple[int, str]:
    """Devolve (id, token). O token só existe em claro aqui; o banco guarda o hash (§12)."""
    email = email.strip()
    if "@" not in email or len(email) > 254:
        raise ValorInvalido("Informe um e-mail válido.")
    grupo_id = conexao.grupo_id
    cargo = repositorio_equipes.obter_cargo(conexao, grupo_id, cargo_id)
    _nao_conceder_alem_do_proprio(conexao, cargo)
    token = segredos.novo_token()
    convite_id = repositorio_equipes.criar_convite(
        conexao,
        grupo_id,
        email,
        cargo_id,
        segredos.hash_do_token(token),
        conexao.usuario_id,
        agora,
        agora + VALIDADE_DO_CONVITE,
    )
    return convite_id, token


def listar_convites(conexao: Conexao) -> list[Convite]:
    return repositorio_equipes.listar_convites(conexao, conexao.grupo_id)


def revogar_convite(conexao: Conexao, convite_id: int, agora: datetime) -> None:
    repositorio_equipes.revogar_convite(conexao, conexao.grupo_id, convite_id, agora)


def aceitar_convite(conexao: Conexao, token: str, usuario_id: int, agora: datetime) -> Grupo:
    """A pessoa autenticada entra na equipe com o cargo do convite. Uso único e com validade."""
    convite = repositorio_equipes.obter_convite_por_hash(conexao, segredos.hash_do_token(token))
    if convite is None:
        raise NaoEncontrado("Convite não encontrado.")
    if convite.revogado_em is not None:
        raise ValorInvalido("Este convite foi revogado.")
    if convite.usado_em is not None:
        raise ValorInvalido("Este convite já foi usado.")
    if convite.expira_em <= agora.isoformat(timespec="seconds"):
        raise ValorInvalido("Este convite expirou. Peça um novo à sua equipe.")
    with transacao(conexao):
        if not repositorio_equipes.marcar_convite_usado(conexao, convite.id, agora):
            raise ValorInvalido("Este convite já foi usado.")
        if repositorio_equipes.obter_membro(conexao, convite.grupo_id, usuario_id) is None:
            repositorio_equipes.adicionar_membro(
                conexao, convite.grupo_id, usuario_id, convite.cargo_id, agora
            )
        else:
            repositorio_equipes.definir_membro_ativo(conexao, convite.grupo_id, usuario_id, True)
    return repositorio_equipes.obter_grupo(conexao, convite.grupo_id)


# --- consentimentos (LGPD, §2.15) ---


def termos_pendentes(conexao: Conexao, usuario_id: int) -> tuple[str, ...]:
    aceitas = repositorio_equipes.versoes_aceitas(conexao, usuario_id)
    return tuple(
        documento
        for documento, versao in legal.vigentes().items()
        if (documento, versao) not in aceitas
    )


def exigir_termos(conexao: Conexao, usuario_id: int) -> None:
    pendentes = termos_pendentes(conexao, usuario_id)
    if pendentes:
        raise TermosPendentes(pendentes)


def aceitar_termos(
    conexao: Conexao, usuario_id: int, agora: datetime, documentos: tuple[str, ...] | None = None
) -> None:
    """Registra o aceite da versão vigente (sem guardar IP, §2.15)."""
    vigentes = legal.vigentes()
    for documento in documentos or tuple(vigentes):
        if documento not in vigentes:
            raise NaoEncontrado(f"Documento '{documento}' não encontrado.")
        repositorio_equipes.registrar_consentimento(
            conexao, usuario_id, documento, vigentes[documento], agora
        )


def meus_consentimentos(conexao: Conexao, usuario_id: int) -> list[tuple[str, str, str]]:
    return repositorio_equipes.listar_consentimentos(conexao, usuario_id)


# --- primeiro administrador (§2.12) ---


def garantir_primeiro_administrador(
    conexao: Conexao, email: str, nome_da_equipe: str, agora: datetime
) -> str | None:
    """Só em instalação vazia (nenhuma equipe): cria a equipe e um convite de administrador.

    Devolve o token do convite (para o operador abrir o link) ou `None` se já há equipe.
    Idempotente: reiniciar a API não cria outra equipe nem outro convite.
    """
    if repositorio_equipes.contar_grupos(conexao):
        return None
    grupo, administrador = criar_equipe(conexao, nome_da_equipe, agora)
    token = segredos.novo_token()
    anterior = conexao.contexto
    conexao.definir_contexto(Contexto(grupo.id, None, frozenset({"equipe:convidar"})))
    try:
        repositorio_equipes.criar_convite(
            conexao,
            grupo.id,
            email,
            administrador.id,
            segredos.hash_do_token(token),
            None,
            agora,
            agora + VALIDADE_DO_CONVITE,
        )
    finally:
        conexao.definir_contexto(anterior)
    return token
