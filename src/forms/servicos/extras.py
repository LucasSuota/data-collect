"""Casos de uso de histórico, busca, notificações, tour e dados da pessoa (§2.14–§2.18).

Regras aqui, HTTP na API: a busca respeita o que o cargo pode ver, a exportação e a exclusão da
conta cumprem a LGPD (§2.15) e a exclusão nunca deixa uma equipe sem quem a administre.
"""

from dataclasses import dataclass
from datetime import datetime

from forms.dominio.models import (
    CargoInvalido,
    Contexto,
    ErroDeCampo,
    Exibicao,
    Formulario,
    NaoEncontrado,
    Registro,
    ValorInvalido,
    ValorJson,
)
from forms.infra.banco import Conexao
from forms.repositorios import equipes as repositorio_equipes
from forms.repositorios import extras as repositorio_extras
from forms.repositorios import formularios as repositorio
from forms.repositorios.extras import Notificacao, Progresso
from forms.repositorios.formularios import EntradaDeHistorico
from forms.servicos import equipes as servico_equipes
from forms.servicos.base import Cache, tipos_calculados_da_versao, transacao
from forms.servicos.consulta import estado_do_registro, exibicao_efetiva

LIMITE_DA_BUSCA = 8
TAMANHO_MINIMO_DO_TERMO = 2
TAMANHO_MAXIMO_DO_TERMO = 100


# --- histórico ---


def historico_do_registro(
    conexao: Conexao, registro_id: int
) -> list[tuple[EntradaDeHistorico, str | None]]:
    """Entradas do mais recente ao mais antigo, com o nome de quem fez (se a pessoa ainda existe).
    Vale também para registro já excluído: o histórico fica (§2.14)."""
    entradas = repositorio.listar_historico(conexao, registro_id)
    if not entradas:
        raise NaoEncontrado(f"Registro {registro_id} não encontrado.")
    nomes = repositorio_extras.nomes_de_usuarios(
        conexao, [e.usuario_id for e in entradas if e.usuario_id is not None]
    )
    return [(e, nomes.get(e.usuario_id or 0)) for e in entradas]


def nomes_de_pessoas(conexao: Conexao, ids: list[int | None]) -> dict[int, str]:
    return repositorio_extras.nomes_de_usuarios(conexao, [i for i in ids if i is not None])


# --- busca global ---


@dataclass(frozen=True)
class ResultadoDaBusca:
    formularios: tuple[Formulario, ...]
    registros: tuple[tuple[int, int, str], ...]  # (registro, formulário, nome do formulário)


def buscar(conexao: Conexao, termo: str) -> ResultadoDaBusca:
    """Busca determinística, sem IA: nome de formulário, `#id` e texto/seleção dos registros.

    Só devolve o que o cargo pode ver; o termo vai sempre como parâmetro (§2.18).
    """
    termo = termo.strip().removeprefix("#")
    if not TAMANHO_MINIMO_DO_TERMO <= len(termo) <= TAMANHO_MAXIMO_DO_TERMO and not termo.isdigit():
        raise ValorInvalido(
            f"Digite de {TAMANHO_MINIMO_DO_TERMO} a {TAMANHO_MAXIMO_DO_TERMO} caracteres."
        )
    contexto = conexao.contexto
    pode_formularios = contexto is not None and contexto.tem("formularios:ver")
    pode_registros = contexto is not None and contexto.tem("registros:ver")
    formularios = (
        tuple(repositorio.buscar_formularios_por_nome(conexao, termo, LIMITE_DA_BUSCA))
        if pode_formularios
        else ()
    )
    registros: list[tuple[int, int, str]] = []
    if pode_registros:
        if termo.isdigit():
            achado = repositorio.registro_existe(conexao, int(termo))
            if achado is not None:
                registros.append((int(termo), achado[0], achado[1]))
        for item in repositorio.buscar_registros_por_texto(conexao, termo, LIMITE_DA_BUSCA):
            if item not in registros:
                registros.append(item)
    return ResultadoDaBusca(formularios, tuple(registros[:LIMITE_DA_BUSCA]))


# --- notificações ---


def listar_notificacoes(conexao: Conexao, limite: int = 30) -> tuple[list[Notificacao], int]:
    usuario_id = _pessoa(conexao)
    return (
        repositorio_extras.listar_notificacoes(conexao, usuario_id, limite),
        repositorio_extras.contar_nao_lidas(conexao, usuario_id),
    )


def marcar_notificacao_lida(conexao: Conexao, notificacao_id: int, agora: datetime) -> None:
    repositorio_extras.marcar_lida(conexao, _pessoa(conexao), notificacao_id, agora)


def _pessoa(conexao: Conexao) -> int:
    usuario_id = conexao.usuario_id
    if usuario_id is None:
        raise ValorInvalido("Pessoa não identificada.")
    return usuario_id


# --- tour e primeiros passos (progresso por pessoa, no servidor) ---


def obter_progresso(conexao: Conexao, usuario_id: int) -> Progresso:
    return repositorio_extras.obter_progresso(conexao, usuario_id)


def atualizar_progresso(
    conexao: Conexao,
    usuario_id: int,
    *,
    tour_concluido: bool,
    passo: int,
    checklist_dispensado: bool,
    agora: datetime,
) -> Progresso:
    if passo < 0 or passo > 50:
        raise ValorInvalido("Passo do tour inválido.")
    progresso = Progresso(tour_concluido, passo, checklist_dispensado)
    repositorio_extras.gravar_progresso(conexao, usuario_id, progresso, agora)
    return progresso


# --- direitos da pessoa (LGPD, §2.15) ---


def exportar_meus_dados(conexao: Conexao, usuario_id: int) -> dict[str, ValorJson]:
    """Tudo que o sistema guarda sobre a pessoa: perfil, aceites, equipes e o que ela criou."""
    pessoa = repositorio_equipes.obter_usuario(conexao, usuario_id)
    equipes: list[ValorJson] = []
    for equipe in servico_equipes.minhas_equipes(conexao, usuario_id):
        anterior = conexao.contexto
        # O Row Level Security só mostra a equipe declarada: uma por vez.
        conexao.definir_contexto(Contexto(equipe.id, usuario_id))
        try:
            criados = conexao.execute(
                "SELECT id, formulario_id, criado_em, atualizado_em FROM registros"
                " WHERE grupo_id = %s AND criado_por = %s ORDER BY id",
                (equipe.id, usuario_id),
            ).fetchall()
            editados = conexao.execute(
                "SELECT COUNT(*) AS n FROM historico_registro WHERE grupo_id = %s"
                " AND usuario_id = %s",
                (equipe.id, usuario_id),
            ).fetchone()
        finally:
            conexao.definir_contexto(anterior)
        cargo, _ = servico_equipes.cargo_e_permissoes(conexao, equipe.cargo_id, equipe.id)
        equipes.append(
            {
                "equipe": equipe.nome,
                "cargo": cargo,
                "ativa": equipe.ativa,
                "registros_criados": [dict(c) for c in criados],
                "alteracoes_feitas": int(editados["n"]) if editados else 0,
            }
        )
    return {
        "pessoa": {
            "id": pessoa.id,
            "nome": pessoa.nome,
            "email": pessoa.email,
            "criado_em": pessoa.criado_em,
            "ultimo_acesso_em": pessoa.ultimo_acesso_em,
        },
        "consentimentos": [
            {"documento": d, "versao": v, "aceito_em": quando}
            for d, v, quando in servico_equipes.meus_consentimentos(conexao, usuario_id)
        ],
        "equipes": equipes,
    }


def excluir_minha_conta(conexao: Conexao, usuario_id: int) -> None:
    """Remove a pessoa e **anonimiza** a autoria (as chaves estrangeiras viram nulas): o trabalho
    da equipe fica. Bloqueia se ela for a única administradora de uma equipe com outras pessoas."""
    with transacao(conexao):
        for equipe in servico_equipes.minhas_equipes(conexao, usuario_id):
            # `cargos` tem RLS: sem a equipe declarada, a lista de membros e a contagem de
            # administradoras vêm vazias e a trava abaixo deixaria a única administradora sair.
            with servico_equipes.declarar_equipe(conexao, equipe.id):
                membros = repositorio_equipes.listar_membros(conexao, equipe.id)
                outros = [m for m in membros if m.usuario_id != usuario_id and m.ativo]
                if not outros:
                    continue
                restam = repositorio_equipes.contar_pessoas_com_permissao(
                    conexao,
                    equipe.id,
                    servico_equipes.PERMISSAO_DE_ADMINISTRACAO,
                    ignorar_usuario=usuario_id,
                )
            if not restam:
                raise CargoInvalido(
                    (
                        ErroDeCampo(
                            "conta",
                            f"Você é a única administradora da equipe '{equipe.nome}'. "
                            "Passe o cargo para outra pessoa antes de excluir a conta.",
                        ),
                    )
                )
        repositorio_equipes.apagar_usuario(conexao, usuario_id)


# --- registros recentes (Início) ---


@dataclass(frozen=True)
class RegistroRecente:
    registro: Registro
    formulario: str
    estado: str
    destaque: tuple[str, str | None, str | None] | None  # (rótulo, valor, unidade)


def recentes_com_estado(conexao: Conexao, limite: int = 5) -> list[RegistroRecente]:
    """Últimos registros alterados, com o estado e o valor em destaque já decididos aqui."""
    resultado = []
    exibicoes: dict[int, Exibicao] = {}  # uma por versão, não uma por registro
    for registro in repositorio.registros_recentes(conexao, limite):
        formulario = repositorio.obter_formulario(conexao, registro.formulario_id).nome
        versao = repositorio.obter_versao(conexao, registro.versao_id)
        if versao.id not in exibicoes:
            tipos = tipos_calculados_da_versao(conexao, versao, Cache())
            exibicoes[versao.id] = exibicao_efetiva(versao, tipos)
        exibicao = exibicoes[versao.id]
        campo = next((c for c in versao.definicao.campos if c.id == exibicao.destaque), None)
        destaque = None
        if campo is not None:
            guardado = registro.dados.get(campo.id)
            valor = guardado.get("valor") if isinstance(guardado, dict) else guardado
            destaque = (campo.rotulo, None if valor is None else str(valor), campo.unidade)
        resultado.append(
            RegistroRecente(
                registro, formulario, estado_do_registro(registro.dados, exibicao.status), destaque
            )
        )
    return resultado
