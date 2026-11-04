"""Matriz endpoint → permissão: a tabela única (AGENTS.md §2.13).

Toda rota da API precisa aparecer aqui. Rota que não aparece é **recusada** (falha fechada), e
`verificar_matriz` derruba a subida da API se alguém esquecer: nenhum endpoint novo nasce sem
decisão de permissão.
"""

from collections.abc import Iterable

from fastapi import FastAPI

type Rota = tuple[str, str]  # (método, caminho com `{parâmetros}`)

# Sem autenticação: saúde, textos legais e a documentação (esta só fora de produção).
PUBLICAS: frozenset[Rota] = frozenset(
    {
        ("GET", "/healthz"),
        ("GET", "/readyz"),
        ("GET", "/legal"),
        ("GET", "/legal/{documento}"),
        ("GET", "/ajuda"),
        ("GET", "/ajuda/{guia}"),
        ("GET", "/catalogo/permissoes"),
    }
)

# Exigem pessoa autenticada, mas não uma equipe (e valem mesmo com termos pendentes).
SEM_EQUIPE: frozenset[Rota] = frozenset(
    {
        ("GET", "/eu"),
        ("GET", "/eu/exportar"),
        ("DELETE", "/eu"),
        ("GET", "/eu/onboarding"),
        ("PUT", "/eu/onboarding"),
        ("GET", "/consentimentos"),
        ("POST", "/consentimentos"),
        ("POST", "/convites/{token}/aceitar"),
    }
)

# Exigem equipe ativa e só isso (qualquer cargo): o que não depende de permissão específica.
QUALQUER_MEMBRO: frozenset[Rota] = frozenset(
    {
        ("GET", "/catalogo"),
        ("POST", "/definicoes/validar"),
        ("POST", "/definicoes/previa"),
        ("GET", "/notificacoes"),
        ("POST", "/notificacoes/{notificacao_id}/lida"),
        ("POST", "/equipe/sair"),
        ("GET", "/equipe"),
    }
)

PERMISSAO_DA_ROTA: dict[Rota, str] = {
    ("POST", "/formularios"): "formularios:publicar",
    ("POST", "/formularios/lote"): "formularios:publicar",
    ("GET", "/formularios"): "formularios:ver",
    ("GET", "/formularios/{formulario_id}"): "formularios:ver",
    ("POST", "/formularios/{formulario_id}/duplicar"): "formularios:publicar",
    ("PUT", "/formularios/{formulario_id}/pasta"): "formularios:organizar",
    ("DELETE", "/formularios/{formulario_id}"): "formularios:excluir",
    ("POST", "/formularios/{formulario_id}/versoes"): "formularios:publicar",
    ("GET", "/formularios/{formulario_id}/versoes"): "formularios:ver",
    ("GET", "/formularios/{formulario_id}/versoes/{versao_id}"): "formularios:ver",
    ("GET", "/formularios/{formulario_id}/rascunho"): "formularios:publicar",
    ("PUT", "/formularios/{formulario_id}/rascunho"): "formularios:publicar",
    ("DELETE", "/formularios/{formulario_id}/rascunho"): "formularios:publicar",
    ("POST", "/formularios/{formulario_id}/rascunho/publicar"): "formularios:publicar",
    ("POST", "/pastas"): "formularios:organizar",
    ("GET", "/pastas"): "formularios:ver",
    ("PUT", "/pastas/{pasta_id}"): "formularios:organizar",
    ("DELETE", "/pastas/{pasta_id}"): "formularios:organizar",
    ("POST", "/formularios/{formulario_id}/registros"): "registros:criar",
    ("GET", "/formularios/{formulario_id}/registros"): "registros:ver",
    ("GET", "/formularios/{formulario_id}/registros/contagens"): "registros:ver",
    ("GET", "/formularios/{formulario_id}/registros/exportar"): "registros:exportar",
    ("GET", "/registros/{registro_id}"): "registros:ver",
    # `registros:editar_proprios` x `editar_todos` depende do registro: o serviço decide (§2.13).
    ("PUT", "/registros/{registro_id}"): "registros:editar_proprios|registros:editar_todos",
    ("DELETE", "/registros/{registro_id}"): "registros:excluir",
    ("GET", "/registros/{registro_id}/historico"): "historico:ver",
    ("GET", "/busca"): "registros:ver",
    ("GET", "/registros/recentes"): "registros:ver",
    ("GET", "/cargos"): "equipe:ver",
    ("POST", "/cargos"): "cargos:editar",
    ("PUT", "/cargos/{cargo_id}"): "cargos:editar",
    ("DELETE", "/cargos/{cargo_id}"): "cargos:editar",
    ("PUT", "/equipe"): "cargos:editar",
    ("GET", "/membros"): "equipe:ver",
    ("PUT", "/membros/{usuario_id}/cargo"): "equipe:atribuir_cargos",
    ("POST", "/membros/{usuario_id}/desativar"): "equipe:convidar",
    ("POST", "/membros/{usuario_id}/reativar"): "equipe:convidar",
    ("GET", "/convites"): "equipe:convidar",
    ("POST", "/convites"): "equipe:convidar",
    ("DELETE", "/convites/{convite_id}"): "equipe:convidar",
    ("POST", "/definicoes/gerar"): "ia:criar_formularios",
    ("POST", "/formularios/{formulario_id}/resumo"): "ia:assistente",
    ("POST", "/assistente/perguntar"): "ia:assistente",
    ("POST", "/chat"): "ia:assistente",
    ("GET", "/chat/conversas"): "ia:assistente",
    ("GET", "/chat/conversas/{conversa_id}"): "ia:assistente",
    ("DELETE", "/chat/conversas/{conversa_id}"): "ia:assistente",
    ("GET", "/ia"): "cargos:editar",
    ("PUT", "/ia"): "cargos:editar",
    ("POST", "/ia/testar"): "cargos:editar",
    ("POST", "/ia/reindexar"): "cargos:editar",
    ("GET", "/ia/uso"): "cargos:editar",
    ("GET", "/templates"): "formularios:publicar",
    ("POST", "/templates/importar"): "formularios:publicar",
}

# Rotas que o próprio FastAPI cria (documentação). Em produção ficam desligadas (§12).
_DO_FASTAPI = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})


def rotas_do_app(app: FastAPI) -> Iterable[Rota]:
    """Toda rota da API, lida do esquema OpenAPI: as rotas incluídas por `include_router` ficam
    embrulhadas em `app.routes`, então varrer a lista de rotas não as enxergaria."""
    esquema = app.openapi()
    app.openapi_schema = None  # o esquema muda se alguém registrar rota depois (testes)
    for caminho, operacoes in esquema["paths"].items():
        for metodo in operacoes:
            yield metodo.upper(), caminho


def classificar(rota: Rota) -> str:
    """`publica`, `sem_equipe`, `qualquer_membro`, a permissão exigida, ou `negada` (fechada)."""
    if rota[1] in _DO_FASTAPI or rota in PUBLICAS:
        return "publica"
    if rota in SEM_EQUIPE:
        return "sem_equipe"
    if rota in QUALQUER_MEMBRO:
        return "qualquer_membro"
    return PERMISSAO_DA_ROTA.get(rota, "negada")


def verificar_matriz(app: FastAPI) -> None:
    """Levanta se alguma rota do app não estiver na matriz."""
    sem_decisao = sorted(r for r in rotas_do_app(app) if classificar(r) == "negada")
    if sem_decisao:
        lista = ", ".join(f"{m} {c}" for m, c in sem_decisao)
        raise RuntimeError(f"Rotas sem decisão de permissão na matriz: {lista}")
