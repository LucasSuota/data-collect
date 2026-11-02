"""Gera o instalador do sistema ATUAL, em três passos (AGENTS.md §4.1).

1. `npm run build` do front;
2. PyInstaller gera o executável do backend (já com o `dist` do front dentro, que é quem o serve);
3. electron-builder monta o instalador (macOS .dmg, Windows NSIS, Linux AppImage).

O PyInstaller não faz compilação cruzada: cada instalador é gerado no próprio sistema, e o CI
roda este script numa matriz com os três. Uso: `uv run --group empacotamento python
empacotamento/empacotar.py` (opcional: `--passo front|backend|instalador`).
"""

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOME_DO_EXECUTAVEL = "forms-backend"


@dataclass(frozen=True)
class Comando:
    passo: str
    argumentos: tuple[str, ...]
    pasta: Path


def comandos(plataforma: str, raiz: Path = RAIZ, npm: str = "npm") -> list[Comando]:
    """Os comandos de cada passo, em ordem. Pura: só monta, não executa (por isso é testável)."""
    separador_do_add_data = ";" if plataforma == "win32" else ":"
    saida = raiz / "empacotamento"
    return [
        Comando("front", (npm, "ci"), raiz / "frontend"),
        Comando("front", (npm, "run", "build"), raiz / "frontend"),
        Comando(
            "backend",
            (
                "uv",
                "run",
                "--locked",
                "--group",
                "empacotamento",
                "pyinstaller",
                "--noconfirm",
                "--clean",
                "--name",
                NOME_DO_EXECUTAVEL,
                # onedir: um executável + pasta, sem o processo "bootloader" extra do onefile,
                # que o Electron não conseguiria encerrar junto com o backend
                "--onedir",
                "--distpath",
                str(saida / "dist"),
                "--workpath",
                str(saida / "build"),
                "--specpath",
                str(saida / "build"),
                "--paths",
                str(raiz / "src"),
                "--add-data",
                f"{raiz / 'frontend' / 'dist'}{separador_do_add_data}frontend_dist",
                # O uvicorn escolhe loops e protocolos por import dinâmico, que o PyInstaller não vê
                "--collect-submodules",
                "uvicorn",
                str(raiz / "src" / "forms" / "app.py"),
            ),
            raiz,
        ),
        Comando("instalador", (npm, "ci"), raiz / "desktop"),
        Comando("instalador", (npm, "run", "build"), raiz / "desktop"),
        Comando(
            "instalador",
            (npm, "exec", "--", "electron-builder", "--publish", "never"),
            raiz / "desktop",
        ),
    ]


def executar(passos: set[str], plataforma: str = sys.platform) -> int:
    npm = shutil.which("npm") or "npm"  # no Windows é npm.cmd
    for comando in comandos(plataforma, npm=npm):
        if comando.passo not in passos:
            continue
        print(f"[{comando.passo}] {' '.join(comando.argumentos)}", flush=True)
        resultado = subprocess.run(comando.argumentos, cwd=comando.pasta, check=False)
        if resultado.returncode != 0:
            print(f"Falhou no passo '{comando.passo}'.", file=sys.stderr)
            return resultado.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o instalador do sistema atual.")
    parser.add_argument("--passo", choices=["front", "backend", "instalador"], help="só um passo")
    args = parser.parse_args(argv)
    passos = {args.passo} if args.passo else {"front", "backend", "instalador"}
    return executar(passos)


if __name__ == "__main__":
    sys.exit(main())
