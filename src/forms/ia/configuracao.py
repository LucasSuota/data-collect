"""Configuração da IA por equipe (AGENTS.md §2.5, §2.15): provedor, modelo e chave cifrada.

A IA nasce **desligada** em cada equipe. Ligar exige o aceite do aviso (para onde vão os dados),
que fica registrado. A chave é cifrada antes de ir ao banco e **nunca** volta pela API. Sem
configuração própria completa, vale o padrão da instância (variáveis de ambiente).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from forms.dominio.models import ErroDeCampo, ValorInvalido
from forms.ia import repositorio
from forms.ia.cliente import (
    ClienteAnthropic,
    ClienteOpenAICompativel,
    IaIndisponivel,
    ProvedorDeLLM,
    criar_cliente,
    validar_base_url,
)
from forms.infra.banco import Conexao
from forms.infra.segredos import Cifra, SegredoIndisponivel, cifra_do_ambiente

PROVEDORES = ("anthropic", "openai_compativel")
MODELOS_PADRAO = {"anthropic": "claude-sonnet-5-5"}
MENSAGEM_DESLIGADA = (
    "A IA está desligada para esta equipe. Quem administra a equipe pode ativá-la em "
    "Configurações > Inteligência artificial."
)


@dataclass(frozen=True)
class ConfigDaEquipe:
    """O que a API mostra: tudo, menos a chave (só `chave_definida`)."""

    ativa: bool
    provedor: str
    base_url: str | None
    modelo: str | None
    modelo_embeddings: str | None
    chave_definida: bool
    consentimento_por: int | None
    consentimento_em: str | None


def obter(conexao: Conexao) -> ConfigDaEquipe:
    gravada = repositorio.obter_config(conexao)
    if gravada is None:
        return ConfigDaEquipe(False, "anthropic", None, None, None, False, None, None)
    return ConfigDaEquipe(
        gravada.ativa,
        gravada.provedor,
        gravada.base_url,
        gravada.modelo,
        gravada.modelo_embeddings,
        gravada.chave_cifrada is not None,
        gravada.consentimento_por,
        gravada.consentimento_em,
    )


def atualizar(
    conexao: Conexao,
    cifra: Cifra | None,
    *,
    ativa: bool,
    aceite_do_aviso: bool,
    provedor: str,
    base_url: str | None,
    modelo: str | None,
    modelo_embeddings: str | None,
    chave: str | None,
    agora: datetime,
) -> ConfigDaEquipe:
    """`chave` ausente mantém a atual; vazia a remove; preenchida a troca (cifrada)."""
    atual = repositorio.obter_config(conexao)
    erros = []
    if provedor not in PROVEDORES:
        erros.append(ErroDeCampo("provedor", "Provedor inexistente."))
    if provedor == "openai_compativel":
        try:
            base_url = validar_base_url(base_url or "")
        except IaIndisponivel as erro:
            erros.append(ErroDeCampo("base_url", str(erro)))
    else:
        base_url = None
    if ativa and not (atual and atual.ativa) and not aceite_do_aviso:
        erros.append(
            ErroDeCampo(
                "aceite_do_aviso",
                "Para ligar a IA, aceite o aviso: trechos dos registros são enviados ao provedor.",
            )
        )
    if erros:
        raise ConfigInvalida(tuple(erros))

    cifrada = atual.chave_cifrada if atual else None
    if chave is not None:
        if chave.strip() == "":
            cifrada = None
        else:
            try:
                if cifra is None:
                    raise SegredoIndisponivel("sem chave-mestra")
                cifrada = cifra.cifrar(chave.strip())
            except SegredoIndisponivel as erro:
                raise ValorInvalido(
                    "O servidor não tem chave-mestra configurada para guardar a chave com "
                    "segurança. Peça a quem administra o servidor."
                ) from erro

    ligou_agora = ativa and not (atual and atual.ativa)
    gravada = repositorio.ConfigGravada(
        ativa=ativa,
        consentimento_por=conexao.usuario_id
        if ligou_agora
        else (atual.consentimento_por if atual else None),
        consentimento_em=agora.isoformat(timespec="seconds")
        if ligou_agora
        else (atual.consentimento_em if atual else None),
        provedor=provedor,
        base_url=base_url,
        modelo=(modelo or "").strip() or None,
        modelo_embeddings=(modelo_embeddings or "").strip() or None,
        chave_cifrada=cifrada,
    )
    repositorio.gravar_config(conexao, gravada, agora)
    return obter(conexao)


class ConfigInvalida(ValorInvalido):
    """Erros por campo da configuração; a API os mostra como 422 no campo certo."""

    def __init__(self, erros: tuple[ErroDeCampo, ...]) -> None:
        super().__init__("; ".join(f"{e.campo}: {e.mensagem}" for e in erros))
        self.erros = erros


def cifra_da_instancia(ambiente: Mapping[str, str] | None = None) -> Cifra | None:
    try:
        return cifra_do_ambiente(os.environ if ambiente is None else ambiente)
    except SegredoIndisponivel:
        return None


def criar_cliente_da_equipe(
    conexao: Conexao, cifra: Cifra | None, ambiente: Mapping[str, str] | None = None
) -> ProvedorDeLLM:
    """O provedor da equipe, ou o padrão da instância se a equipe não configurou o seu.

    IA desligada na equipe → `IaIndisponivel` com a mensagem para a pessoa, mesmo que a
    instância tenha chave: sem o aceite da equipe, nada é enviado (§2.15).
    """
    gravada = repositorio.obter_config(conexao)
    if gravada is None or not gravada.ativa:
        raise IaIndisponivel(MENSAGEM_DESLIGADA)
    ambiente = os.environ if ambiente is None else ambiente
    modelo = gravada.modelo or MODELOS_PADRAO.get(gravada.provedor)
    chave: str | None = None
    if gravada.chave_cifrada is not None:
        try:
            if cifra is None:
                raise SegredoIndisponivel("sem chave-mestra")
            chave = cifra.decifrar(gravada.chave_cifrada)
        except SegredoIndisponivel as erro:
            raise IaIndisponivel(
                "Não foi possível ler a chave da IA desta equipe. Cadastre a chave de novo."
            ) from erro
    if gravada.provedor == "openai_compativel" and gravada.base_url and modelo:
        return ClienteOpenAICompativel(
            gravada.base_url, chave, modelo, modelo_de_vetores=gravada.modelo_embeddings
        )
    if gravada.provedor == "anthropic" and chave and modelo:
        return ClienteAnthropic(chave, modelo)
    return criar_cliente(ambiente)  # padrão da instância
