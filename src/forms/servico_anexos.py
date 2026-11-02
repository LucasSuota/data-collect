"""Casos de uso dos anexos: o upload em duas etapas e os arquivos `.webp` da pasta de dados (§2.8).

O I/O de arquivo fica aqui, nunca em `fotos.py` (que só transforma bytes) nem no repositório
(que só guarda os metadados). A pasta de dados entra por parâmetro.
"""

import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path

from forms import fotos, repositorio
from forms.models import NaoEncontrado
from forms.repositorio import Anexo
from forms.servico_base import transacao

PASTA_DOS_ANEXOS = "anexos"
# Anexo enviado e nunca vinculado a um registro por mais tempo que isto é lixo (§2.8).
TEMPO_DE_VIDA_DO_ORFAO = timedelta(hours=24)


def guardar_anexo(
    conexao: sqlite3.Connection, pasta_de_dados: Path, conteudo: bytes, agora: datetime
) -> Anexo:
    """Processa a imagem, grava `<uuid>.webp` e registra os metadados. O original é descartado.

    O nome do arquivo é gerado aqui, nunca o enviado pelo cliente (sem path traversal, §12).
    Imagem inválida levanta `FotoInvalida` e não deixa arquivo nem linha.
    """
    foto = fotos.processar_foto(conteudo)
    caminho_relativo = f"{PASTA_DOS_ANEXOS}/{uuid.uuid4().hex}.webp"
    arquivo = pasta_de_dados / PASTA_DOS_ANEXOS / Path(caminho_relativo).name
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(foto.dados)
    try:
        with transacao(conexao):
            return repositorio.criar_anexo(
                conexao,
                caminho_relativo,
                largura=foto.largura,
                altura=foto.altura,
                tamanho_bytes=foto.tamanho_bytes,
                agora=agora,
            )
    except BaseException:
        arquivo.unlink(missing_ok=True)  # sem linha, o arquivo seria órfão para sempre
        raise


def ler_anexo(conexao: sqlite3.Connection, pasta_de_dados: Path, anexo_id: int) -> bytes:
    """Bytes do WebP guardado, para o `GET /anexos/{id}`."""
    anexo = repositorio.obter_anexo(conexao, anexo_id)
    arquivo = _arquivo_do_anexo(pasta_de_dados, anexo.caminho)
    try:
        return arquivo.read_bytes()
    except FileNotFoundError as erro:
        raise NaoEncontrado(f"O arquivo do anexo {anexo_id} não foi encontrado.") from erro


def limpar_anexos_orfaos(conexao: sqlite3.Connection, pasta_de_dados: Path, agora: datetime) -> int:
    """Remove anexos nunca vinculados há mais de 24 h (chamado na inicialização do app)."""
    with transacao(conexao):
        orfaos = repositorio.listar_anexos_orfaos(
            conexao, criados_antes_de=agora - TEMPO_DE_VIDA_DO_ORFAO
        )
        for anexo in orfaos:
            repositorio.apagar_anexo(conexao, anexo.id)
    apagar_arquivos(pasta_de_dados, [anexo.caminho for anexo in orfaos])
    return len(orfaos)


def apagar_arquivos(pasta_de_dados: Path, caminhos: Iterable[str]) -> None:
    """Apaga os arquivos *depois* do commit: se o commit falhar, a foto ainda é do registro."""
    for caminho in caminhos:
        try:
            _arquivo_do_anexo(pasta_de_dados, caminho).unlink(missing_ok=True)
        except NaoEncontrado:
            continue  # caminho fora da pasta de dados: nunca apagar nada lá


def _arquivo_do_anexo(pasta_de_dados: Path, caminho: str) -> Path:
    """Resolve o caminho guardado (sempre com `/`) e garante que não sai da pasta de dados."""
    base = pasta_de_dados.resolve()
    arquivo = (base / Path(*caminho.split("/"))).resolve()
    if not arquivo.is_relative_to(base):
        raise NaoEncontrado("O caminho do anexo está fora da pasta de dados.")
    return arquivo
