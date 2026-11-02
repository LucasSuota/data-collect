"""Entrada do backend no app instalável (AGENTS.md §4.1): só monta as peças.

Sobe a API em `127.0.0.1` numa porta livre, serve o build do front na mesma origem e imprime
`{"porta": N}` como primeira linha da saída, que o Electron lê. Sem regra de negócio.
"""

import json
import os
import socket
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO

import platformdirs

from forms.api import Configuracao, criar_app, descobrir_extensoes

NOME_DO_APP = "ConstrutorDeFormularios"
ENDERECO_LOCAL = "127.0.0.1"


class TokenAusente(Exception):
    """O Electron gera o token a cada execução; sem ele a API recusaria tudo."""


def configuracao_do_app(
    ambiente: Mapping[str, str], pasta_do_usuario: Path | None = None
) -> Configuracao:
    """Banco e fotos na pasta de dados do sistema, nunca dentro do pacote do app."""
    token = (ambiente.get("FORMS_TOKEN") or "").strip()
    if not token:
        raise TokenAusente("A variável FORMS_TOKEN não foi definida: o Electron deve passá-la.")
    pasta = pasta_do_usuario or Path(
        ambiente.get("FORMS_DATA_DIR") or platformdirs.user_data_dir(NOME_DO_APP, appauthor=False)
    )
    return Configuracao(
        banco=pasta / "forms.db",
        pasta_de_dados=pasta,
        token=token,
        # O app instalado jamais dispensa o token, mesmo que a variável de desenvolvimento exista.
        dispensar_token=False,
        origens_cors=(),  # mesma origem: não há CORS
    )


def localizar_front(
    ambiente: Mapping[str, str],
    empacotado: bool | None = None,
    base_do_executavel: Path | None = None,
) -> Path | None:
    """Onde está o `frontend/dist`: no executável empacotado, na variável ou no repositório."""
    if (explicito := ambiente.get("FORMS_FRONTEND_DIST")) is not None:
        candidato = Path(explicito)
    else:
        if empacotado is None:
            empacotado = bool(getattr(sys, "frozen", False))
        if empacotado:
            # O PyInstaller descompacta os dados do executável em `sys._MEIPASS`.
            base = base_do_executavel or Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            candidato = base / "frontend_dist"
        else:
            candidato = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return candidato if (candidato / "index.html").is_file() else None


def abrir_soquete_local() -> socket.socket:
    """Reserva uma porta livre só em 127.0.0.1 e já a deixa escutando.

    O soquete é entregue ao uvicorn: não se "acha uma porta livre e fecha", o que deixaria uma
    janela para outro processo ocupá-la antes do servidor subir.
    """
    soquete = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    soquete.bind((ENDERECO_LOCAL, 0))
    soquete.listen(128)
    return soquete


def primeira_linha(porta: int) -> str:
    return json.dumps({"porta": porta})


def _servir_com_uvicorn(app, soquete: socket.socket) -> None:  # pragma: no cover - roda o servidor
    import uvicorn

    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[soquete])


def main(
    ambiente: Mapping[str, str] | None = None,
    saida: TextIO | None = None,
    servir: Callable = _servir_com_uvicorn,
) -> int:
    ambiente = os.environ if ambiente is None else ambiente
    saida = sys.stdout if saida is None else saida
    try:
        configuracao = configuracao_do_app(ambiente)
    except TokenAusente as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

    configuracao.pasta_de_dados.mkdir(parents=True, exist_ok=True)
    app = criar_app(
        configuracao,
        pasta_do_front=localizar_front(ambiente),
        extensoes=descobrir_extensoes(),
    )
    soquete = abrir_soquete_local()
    try:
        # A primeira linha da saída: o Electron a lê para saber a porta (§4.1).
        print(primeira_linha(soquete.getsockname()[1]), file=saida, flush=True)
        servir(app, soquete)
    finally:
        soquete.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
