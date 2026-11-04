"""Exporta o `openapi.json` que o `frontend/` consome com o `openapi-typescript` (AGENTS.md §5.3).

`--conferir` não grava: sai com 1 se o arquivo estiver desatualizado. É o que o CI do front usa
para falhar quando alguém muda a API sem regenerar os tipos TypeScript.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from forms.api import Configuracao, criar_app, descobrir_extensoes

SAIDA_PADRAO = Path("openapi.json")


def gerar() -> str:
    # O app é montado sem abrir conexão: só o esquema importa. Determinístico: mesma ordem de
    # chaves da definição, sem espaço variável, `\n` final.
    app = criar_app(
        Configuracao(dsn="postgresql://openapi/openapi", origens_cors=("http://localhost:5173",)),
        extensoes=descobrir_extensoes(),
    )
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="forms-openapi", description="Exporta o openapi.json da API."
    )
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO, help="arquivo de saída")
    parser.add_argument(
        "--conferir", action="store_true", help="não grava; falha se estiver desatualizado"
    )
    args = parser.parse_args(argv)

    conteudo = gerar()
    if args.conferir:
        atual = args.saida.read_text(encoding="utf-8") if args.saida.exists() else None
        if atual != conteudo:
            print(
                f"O arquivo {args.saida} está desatualizado: gere de novo com forms-openapi.",
                file=sys.stderr,
            )
            return 1
        return 0
    args.saida.write_text(conteudo, encoding="utf-8", newline="\n")
    print(f"OpenAPI gravado em {args.saida}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
