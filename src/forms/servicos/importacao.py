"""Importa o `forms.db` da versão anterior (SQLite, uma pessoa só) para uma equipe (§2.4).

Para quem já tinha dados antes da versão web. Preserva versões, vínculos, datas e a ordem; os ids
mudam (o Postgres os gera) e as referências entre registros são remapeadas. **Fotos foram
removidas do produto**: o campo `foto` sai das definições e os valores são descartados, com
aviso. É a única exceção à imutabilidade das versões, porque o tipo deixou de existir.
Só roda em equipe vazia, numa transação: ou entra tudo, ou nada.
"""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from forms.dominio.models import ErroDeDominio, ValorJson
from forms.infra.banco import Conexao
from forms.repositorios import formularios as repositorio
from forms.servicos.base import transacao


class ImportacaoInvalida(ErroDeDominio):
    """O arquivo não é um banco da versão anterior, ou a equipe de destino já tem dados."""


@dataclass
class Relatorio:
    pastas: int = 0
    formularios: int = 0
    versoes: int = 0
    registros: int = 0
    referencias: int = 0
    avisos: list[str] = field(default_factory=list)


def importar_sqlite(conexao: Conexao, caminho: Path, agora: datetime) -> Relatorio:
    if repositorio.listar_formularios(conexao) or repositorio.listar_pastas(conexao):
        raise ImportacaoInvalida(
            "A equipe já tem formulários ou pastas: importe numa equipe vazia."
        )
    if not caminho.is_file():
        raise ImportacaoInvalida(f"Arquivo '{caminho}' não encontrado.")
    origem = sqlite3.connect(f"file:{caminho.resolve().as_posix()}?mode=ro", uri=True)
    origem.row_factory = sqlite3.Row
    try:
        _conferir_esquema(origem)
        relatorio = Relatorio()
        with transacao(conexao):
            _importar(conexao, origem, agora, relatorio)
        return relatorio
    finally:
        origem.close()


def _conferir_esquema(origem: sqlite3.Connection) -> None:
    tabelas = {r[0] for r in origem.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    faltam = {"formularios", "versoes_formulario", "registros"} - tabelas
    if faltam:
        raise ImportacaoInvalida(
            "Este arquivo não parece um banco do data-collect (faltam as tabelas: "
            + ", ".join(sorted(faltam))
            + ")."
        )


def _importar(
    conexao: Conexao, origem: sqlite3.Connection, agora: datetime, relatorio: Relatorio
) -> None:
    tabelas = {r[0] for r in origem.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    pastas = _importar_pastas(conexao, origem, agora, relatorio) if "pastas" in tabelas else {}

    formularios: dict[int, int] = {}
    campos_de_foto: dict[int, set[str]] = {}  # versão antiga -> ids de campos `foto`
    campos_de_referencia: dict[int, set[str]] = {}  # versão antiga -> ids de campos `referencia`
    versoes: dict[int, int] = {}
    colunas = {r[1] for r in origem.execute("PRAGMA table_info(formularios)")}
    for linha in origem.execute("SELECT * FROM formularios ORDER BY id"):
        pasta = pastas.get(linha["pasta_id"]) if "pasta_id" in colunas else None
        criado = repositorio.criar_formulario(
            conexao, linha["nome"], _momento(linha["criado_em"], agora), pasta
        )
        formularios[linha["id"]] = criado.id
        relatorio.formularios += 1

    for linha in origem.execute("SELECT * FROM versoes_formulario ORDER BY formulario_id, numero"):
        definicao = json.loads(linha["definicao"])
        fotos = {c["id"] for c in definicao.get("campos", []) if c.get("tipo") == "foto"}
        if fotos:
            definicao["campos"] = [c for c in definicao["campos"] if c.get("tipo") != "foto"]
            relatorio.avisos.append(
                f"Versão {linha['numero']} do formulário {linha['formulario_id']}: "
                f"campo(s) de foto removido(s): {', '.join(sorted(fotos))}."
            )
        campos_de_foto[linha["id"]] = fotos
        campos_de_referencia[linha["id"]] = {
            c["id"] for c in definicao.get("campos", []) if c.get("tipo") == "referencia"
        }
        from forms.dominio.models import Definicao  # noqa: PLC0415 - só aqui

        nova = repositorio.inserir_versao(
            conexao,
            formularios[linha["formulario_id"]],
            Definicao.de_json(definicao),
            _momento(linha["publicada_em"], agora),
        )
        versoes[linha["id"]] = nova.id
        relatorio.versoes += 1

    dependencias: dict[int, set[int]] = {}
    if "dependencias_formulario" in tabelas:
        for linha in origem.execute("SELECT * FROM dependencias_formulario"):
            dependencias.setdefault(linha["formulario_id"], set()).add(linha["depende_de_id"])
    for formulario, origens in dependencias.items():
        repositorio.registrar_dependencias(
            conexao, formularios[formulario], {formularios[o] for o in origens}
        )

    registros: dict[int, int] = {}
    dados_originais: dict[int, tuple[dict[str, ValorJson], set[str]]] = {}
    for linha in origem.execute("SELECT * FROM registros ORDER BY id"):
        dados: dict[str, ValorJson] = json.loads(linha["dados"])
        for foto in campos_de_foto.get(linha["versao_id"], set()):
            if dados.pop(foto, None) is not None:
                relatorio.avisos.append(f"Registro {linha['id']}: fotos descartadas.")
        novo = repositorio.inserir_registro(
            conexao,
            formularios[linha["formulario_id"]],
            versoes[linha["versao_id"]],
            dados,
            _momento(linha["criado_em"], agora),
            atualizado_em=_momento(linha["atualizado_em"], agora),
        )
        repositorio.registrar_historico(
            conexao, novo.id, "criado", None, agora, "importado do banco anterior"
        )
        registros[linha["id"]] = novo.id
        dados_originais[novo.id] = (dados, campos_de_referencia.get(linha["versao_id"], set()))
        relatorio.registros += 1

    # O valor de um campo `referencia` é o id do registro de origem: com os ids novos, remapeia.
    for novo_id, (dados, campos) in dados_originais.items():
        trocados = {c: registros[dados[c]] for c in campos if isinstance(dados.get(c), int)}
        if trocados:
            repositorio.reescrever_dados(conexao, novo_id, {**dados, **trocados})

    if "referencias_registro" in tabelas:
        por_registro: dict[int, dict[str, int]] = {}
        for linha in origem.execute("SELECT * FROM referencias_registro"):
            por_registro.setdefault(linha["registro_id"], {})[linha["campo_id"]] = registros[
                linha["destino_id"]
            ]
        for antigo, referencias in por_registro.items():
            repositorio.substituir_referencias(conexao, registros[antigo], referencias)
            relatorio.referencias += len(referencias)


def _importar_pastas(
    conexao: Conexao, origem: sqlite3.Connection, agora: datetime, relatorio: Relatorio
) -> dict[int, int]:
    linhas = {r["id"]: r for r in origem.execute("SELECT * FROM pastas ORDER BY id")}
    mapa: dict[int, int] = {}

    def criar(id_antigo: int) -> int:
        if id_antigo in mapa:
            return mapa[id_antigo]
        linha = linhas[id_antigo]
        pai = criar(linha["pasta_pai_id"]) if linha["pasta_pai_id"] is not None else None
        nova = repositorio.criar_pasta(
            conexao, linha["nome"], pai, _momento(linha["criado_em"], agora)
        )
        mapa[id_antigo] = nova.id
        relatorio.pastas += 1
        return nova.id

    for id_antigo in linhas:
        criar(id_antigo)
    return mapa


def _momento(texto: str | None, padrao: datetime) -> datetime:
    """Datas do banco antigo eram texto ISO; sem fuso, assumimos UTC (o app gravava em UTC)."""
    if not texto:
        return padrao
    momento = datetime.fromisoformat(texto)
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)
