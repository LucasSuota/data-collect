"""Guias da central de ajuda (AGENTS.md §2.16): `ajuda/*.md`, a mesma pasta que alimenta o chatbot.

O primeiro título (`# ...`) de cada arquivo é o título do guia. O conteúdo é Markdown e a API só o
entrega como texto: quem exibe (o front) o renderiza sem HTML cru (§12).
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from forms.dominio.models import NaoEncontrado

_NOME = re.compile(r"[a-z0-9-]+")
_TITULO = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Ordem de leitura sugerida; guia novo que não estiver aqui vai depois, em ordem alfabética.
ORDEM = (
    "primeiros-passos",
    "formularios",
    "tipos-de-campo",
    "formulas",
    "vinculos",
    "pastas",
    "registros",
    "exportar",
    "equipe-e-cargos",
    "privacidade-e-ia",
)


@dataclass(frozen=True)
class Guia:
    id: str
    titulo: str
    markdown: str


def pasta_de_ajuda() -> Path:
    padrao = Path(__file__).resolve().parents[3] / "ajuda"
    return Path(os.environ.get("FORMS_AJUDA_DIR") or padrao)


def listar(pasta: Path | None = None) -> list[Guia]:
    base = pasta or pasta_de_ajuda()
    if not base.is_dir():
        return []
    guias = [_ler(arquivo) for arquivo in base.glob("*.md") if _NOME.fullmatch(arquivo.stem)]
    return sorted(guias, key=lambda g: (ORDEM.index(g.id) if g.id in ORDEM else len(ORDEM), g.id))


def ler(guia: str, pasta: Path | None = None) -> Guia:
    # O nome vira caminho: só `[a-z0-9-]` entra, então não há `..` nem `/` (path traversal, §12).
    if not _NOME.fullmatch(guia):
        raise NaoEncontrado(f"Guia '{guia}' não encontrado.")
    arquivo = (pasta or pasta_de_ajuda()) / f"{guia}.md"
    if not arquivo.is_file():
        raise NaoEncontrado(f"Guia '{guia}' não encontrado.")
    return _ler(arquivo)


def _ler(arquivo: Path) -> Guia:
    texto = arquivo.read_text(encoding="utf-8")
    achado = _TITULO.search(texto)
    return Guia(arquivo.stem, achado.group(1) if achado else arquivo.stem, texto.strip())
