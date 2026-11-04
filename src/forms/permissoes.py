"""Catálogo único de permissões e cargos de partida (AGENTS.md §2.13).

É a fonte da matriz endpoint → permissão, da tela de cargos e do `GET /eu`: nenhuma lista
paralela. As 17 permissões e os textos vêm do design de referência.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Permissao:
    id: str
    grupo: str
    rotulo: str
    descricao: str


@dataclass(frozen=True)
class CargoPadrao:
    nome: str
    descricao: str
    permissoes: frozenset[str]


FORMULARIOS = "Formulários"
REGISTROS = "Registros"
IA = "Inteligência artificial"
EQUIPE = "Equipe e sistema"

PERMISSOES: tuple[Permissao, ...] = (
    Permissao(
        "formularios:ver",
        FORMULARIOS,
        "Ver formulários",
        "Abrir a lista e a versão atual de cada formulário.",
    ),
    Permissao(
        "formularios:publicar",
        FORMULARIOS,
        "Criar e publicar versões",
        "Usar o construtor. Cada publicação gera uma versão nova, sem quebrar registros antigos.",
    ),
    Permissao(
        "formularios:excluir",
        FORMULARIOS,
        "Excluir formulários",
        "Só vale para formulários sem registros e sem dependentes.",
    ),
    Permissao(
        "formularios:organizar",
        FORMULARIOS,
        "Organizar em pastas",
        "Criar, renomear e mover pastas e formulários.",
    ),
    Permissao("registros:ver", REGISTROS, "Ver registros", "Listar, filtrar e abrir registros."),
    Permissao(
        "registros:criar", REGISTROS, "Criar registros", "Preencher formulários, com localização."
    ),
    Permissao(
        "registros:editar_proprios",
        REGISTROS,
        "Editar os próprios registros",
        "Apenas os que a pessoa criou.",
    ),
    Permissao(
        "registros:editar_todos",
        REGISTROS,
        "Editar registros de outras pessoas",
        "Recalcula em cascata os registros que dependem do editado.",
    ),
    Permissao(
        "registros:excluir",
        REGISTROS,
        "Excluir registros",
        "Bloqueado se outro registro depende dele.",
    ),
    Permissao(
        "registros:exportar",
        REGISTROS,
        "Exportar CSV",
        "Baixar a planilha com os mesmos filtros da lista.",
    ),
    Permissao(
        "ia:criar_formularios",
        IA,
        "Criar formulários com IA",
        "A IA só propõe; a pessoa revisa e publica.",
    ),
    Permissao(
        "ia:assistente",
        IA,
        "Assistente e resumos",
        "Perguntar sobre o app e sobre os dados e resumir registros.",
    ),
    Permissao("equipe:ver", EQUIPE, "Ver a equipe", "Lista de pessoas e cargos."),
    Permissao(
        "equipe:convidar",
        EQUIPE,
        "Convidar e desativar pessoas",
        "Enviar convites e suspender acessos.",
    ),
    Permissao("equipe:atribuir_cargos", EQUIPE, "Atribuir cargos", "Mudar o cargo de uma pessoa."),
    Permissao(
        "historico:ver",
        EQUIPE,
        "Ver o histórico de alterações",
        "Quem criou, editou ou excluiu o quê, e quando.",
    ),
    Permissao("cargos:editar", EQUIPE, "Editar cargos e permissões", "A tela de cargos."),
)

IDS_DE_PERMISSAO: frozenset[str] = frozenset(p.id for p in PERMISSOES)

# Administrador é o cargo que nunca falta (§2.13): o servidor o recria se a equipe ficar sem.
NOME_DO_ADMINISTRADOR = "Administrador"

CARGOS_PADRAO: tuple[CargoPadrao, ...] = (
    CargoPadrao(
        NOME_DO_ADMINISTRADOR, "Controle total, inclusive equipe e cargos.", IDS_DE_PERMISSAO
    ),
    CargoPadrao(
        "Gestor",
        "Acompanha a equipe e os registros; não altera formulários.",
        frozenset(
            {
                "formularios:ver",
                "registros:ver",
                "registros:exportar",
                "equipe:ver",
                "historico:ver",
            }
        ),
    ),
    CargoPadrao(
        "Engenheiro",
        "Monta formulários e revisa qualquer registro.",
        frozenset(
            {
                "formularios:ver",
                "formularios:publicar",
                "formularios:excluir",
                "formularios:organizar",
                "registros:ver",
                "registros:criar",
                "registros:editar_proprios",
                "registros:editar_todos",
                "registros:exportar",
                "ia:criar_formularios",
                "ia:assistente",
            }
        ),
    ),
    CargoPadrao(
        "Técnico",
        "Preenche em campo e edita só o que criou.",
        frozenset(
            {
                "formularios:ver",
                "registros:ver",
                "registros:criar",
                "registros:editar_proprios",
            }
        ),
    ),
    CargoPadrao(
        "Visualizador",
        "Consulta formulários e registros sem alterar nada.",
        frozenset({"formularios:ver", "registros:ver"}),
    ),
)
