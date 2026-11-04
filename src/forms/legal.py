"""Textos legais versionados (AGENTS.md §2.15): `legal/termos.md` e `legal/privacidade.md`.

A primeira linha de cada arquivo é `versao: AAAA-MM-DD`. Mudou o texto, muda a versão, e quem
já tinha aceitado precisa aceitar de novo antes de continuar.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from forms.models import NaoEncontrado

DOCUMENTOS = ("termos", "privacidade")
TITULOS = {"termos": "Termos de Uso", "privacidade": "Política de Privacidade"}


@dataclass(frozen=True)
class Documento:
    id: str
    titulo: str
    versao: str
    markdown: str


def pasta_legal() -> Path:
    # Em dev e na imagem, `legal/` fica na raiz do repositório, ao lado de `src/`.
    padrao = Path(__file__).resolve().parents[2] / "legal"
    return Path(os.environ.get("FORMS_LEGAL_DIR") or padrao)


def ler(documento: str, pasta: Path | None = None) -> Documento:
    if documento not in DOCUMENTOS:
        raise NaoEncontrado(f"Documento '{documento}' não encontrado.")
    arquivo = (pasta or pasta_legal()) / f"{documento}.md"
    primeira, _, resto = arquivo.read_text(encoding="utf-8").partition("\n")
    prefixo = "versao:"
    if not primeira.startswith(prefixo):
        raise ValueError(f"{arquivo} deve começar com '{prefixo} AAAA-MM-DD'.")
    return Documento(documento, TITULOS[documento], primeira[len(prefixo) :].strip(), resto.strip())


def vigentes(pasta: Path | None = None) -> dict[str, str]:
    """Versão vigente de cada documento."""
    return {d: ler(d, pasta).versao for d in DOCUMENTOS}
