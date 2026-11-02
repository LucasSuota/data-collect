"""Divide os procedimentos em Markdown (`docs/`) em trechos para a busca (AGENTS.md §2.5)."""

import re
from dataclasses import dataclass
from pathlib import Path

MAXIMO_DE_CARACTERES = 800
_TITULO = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


@dataclass(frozen=True)
class Trecho:
    arquivo: str
    titulo: str  # caminho dos títulos: "Moldagem > Cura"
    texto: str


def dividir_em_trechos(
    arquivo: str, texto: str, maximo_de_caracteres: int = MAXIMO_DE_CARACTERES
) -> list[Trecho]:
    """Um trecho por seção (título), quebrado por parágrafos se passar do limite."""
    trechos: list[Trecho] = []
    titulos: list[tuple[int, str]] = []  # (nível, texto) da pilha de títulos
    corpo: list[str] = []
    em_codigo = False

    def fechar_secao() -> None:
        conteudo = "\n".join(corpo).strip()
        corpo.clear()
        if not conteudo:
            return
        caminho = " > ".join(t for _, t in titulos)
        for pedaco in _quebrar(conteudo, maximo_de_caracteres):
            trechos.append(Trecho(arquivo, caminho, pedaco))

    for linha in texto.splitlines():
        if linha.strip().startswith("```"):
            em_codigo = not em_codigo
        achado = None if em_codigo else _TITULO.match(linha)
        if achado is None:
            corpo.append(linha)
            continue
        fechar_secao()
        nivel = len(achado.group(1))
        # Um título de nível igual ou menor encerra os anteriores (não se acumula).
        while titulos and titulos[-1][0] >= nivel:
            titulos.pop()
        titulos.append((nivel, achado.group(2)))
    fechar_secao()
    return trechos


def carregar_documentos(pasta: Path) -> list[Trecho]:
    """Todos os `.md` da pasta (e subpastas), em ordem, com o caminho relativo como arquivo."""
    if not pasta.is_dir():
        return []
    trechos: list[Trecho] = []
    for caminho in sorted(pasta.rglob("*.md")):
        nome = caminho.relative_to(pasta).as_posix()
        trechos.extend(dividir_em_trechos(nome, caminho.read_text(encoding="utf-8")))
    return trechos


def _quebrar(conteudo: str, maximo: int) -> list[str]:
    if len(conteudo) <= maximo:
        return [conteudo]
    pedacos: list[str] = []
    atual = ""
    for paragrafo in re.split(r"\n\s*\n", conteudo):
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        candidato = f"{atual}\n\n{paragrafo}" if atual else paragrafo
        if len(candidato) <= maximo or not atual:
            atual = candidato  # parágrafo maior que o limite vai inteiro, não cortado no meio
        else:
            pedacos.append(atual)
            atual = paragrafo
    if atual:
        pedacos.append(atual)
    return pedacos
