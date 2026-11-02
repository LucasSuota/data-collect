import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
_especificacao = importlib.util.spec_from_file_location(
    "empacotar", RAIZ / "empacotamento" / "empacotar.py"
)
empacotar = importlib.util.module_from_spec(_especificacao)
_especificacao.loader.exec_module(empacotar)


def _por_passo(plataforma="linux", raiz=Path("/repo")):
    agrupados = {}
    for comando in empacotar.comandos(plataforma, raiz):
        agrupados.setdefault(comando.passo, []).append(comando)
    return agrupados


def test_sao_tres_passos_na_ordem_front_backend_instalador():
    # act
    passos = [c.passo for c in empacotar.comandos("linux", Path("/repo"))]

    # assert: o front vem antes do backend (que o embute) e o instalador por último
    ordem = list(dict.fromkeys(passos))
    assert ordem == ["front", "backend", "instalador"]


def test_front_instala_pelo_lockfile_e_roda_o_build():
    # act
    front = _por_passo()["front"]

    # assert
    assert [c.argumentos for c in front] == [("npm", "ci"), ("npm", "run", "build")]
    assert all(c.pasta == Path("/repo/frontend") for c in front)


def test_pyinstaller_usa_o_lockfile_o_grupo_de_empacotamento_e_onedir():
    # act
    (backend,) = _por_passo()["backend"]
    args = backend.argumentos

    # assert
    assert args[:6] == ("uv", "run", "--locked", "--group", "empacotamento", "pyinstaller")
    assert "--onedir" in args and "--onefile" not in args
    assert args[args.index("--name") + 1] == "forms-backend"
    assert args[-1] == str(Path("/repo/src/forms/app.py"))


def test_o_dist_do_front_vai_dentro_do_executavel_como_frontend_dist():
    # act
    (backend,) = _por_passo("linux")["backend"]
    argumento = backend.argumentos[backend.argumentos.index("--add-data") + 1]

    # assert: é o nome que `app.localizar_front` procura em sys._MEIPASS
    assert argumento == f"{Path('/repo/frontend/dist')}:frontend_dist"


def test_o_separador_do_add_data_e_ponto_e_virgula_so_no_windows():
    # act
    (windows,) = _por_passo("win32", Path("C:/repo"))["backend"]
    (mac,) = _por_passo("darwin")["backend"]

    # assert
    assert windows.argumentos[windows.argumentos.index("--add-data") + 1].endswith(";frontend_dist")
    assert mac.argumentos[mac.argumentos.index("--add-data") + 1].endswith(":frontend_dist")


def test_uvicorn_tem_os_submodulos_coletados_por_causa_dos_imports_dinamicos():
    # act
    (backend,) = _por_passo()["backend"]

    # assert
    assert backend.argumentos[backend.argumentos.index("--collect-submodules") + 1] == "uvicorn"


def test_o_pyinstaller_nao_escreve_dentro_do_codigo_fonte():
    # act
    (backend,) = _por_passo()["backend"]
    args = backend.argumentos

    # assert: saídas em empacotamento/ (que o .gitignore ignora), nunca em src/
    for opcao in ("--distpath", "--workpath", "--specpath"):
        assert args[args.index(opcao) + 1].startswith(str(Path("/repo/empacotamento")))


def test_instalador_constroi_o_desktop_e_chama_o_electron_builder_sem_publicar():
    # act
    instalador = _por_passo()["instalador"]

    # assert
    assert [c.argumentos for c in instalador] == [
        ("npm", "ci"),
        ("npm", "run", "build"),
        ("npm", "exec", "--", "electron-builder", "--publish", "never"),
    ]
    assert all(c.pasta == Path("/repo/desktop") for c in instalador)


def test_o_executavel_empacotado_tem_o_nome_que_o_electron_procura():
    # assert: `desktop/src/logica.ts` espera resources/backend/forms-backend
    logica = (RAIZ / "desktop" / "src" / "logica.ts").read_text(encoding="utf-8")
    config = (RAIZ / "desktop" / "electron-builder.yml").read_text(encoding="utf-8")

    assert empacotar.NOME_DO_EXECUTAVEL == "forms-backend"
    assert '"forms-backend"' in logica or "forms-backend" in logica
    assert "from: ../empacotamento/dist/forms-backend" in config and "to: backend" in config


def test_so_os_passos_pedidos_sao_executados(monkeypatch):
    # arrange
    executados = []
    monkeypatch.setattr(
        empacotar.subprocess,
        "run",
        lambda args, cwd, check: executados.append(args) or type("R", (), {"returncode": 0})(),
    )

    # act
    codigo = empacotar.executar({"front"}, "linux")

    # assert
    assert codigo == 0 and len(executados) == 2 and all("pyinstaller" not in a for a in executados)


def test_para_no_primeiro_passo_que_falha_e_devolve_o_codigo(monkeypatch, capsys):
    # arrange
    chamadas = []

    def falha(args, cwd, check):
        chamadas.append(args)
        return type("R", (), {"returncode": 7})()

    monkeypatch.setattr(empacotar.subprocess, "run", falha)

    # act
    codigo = empacotar.executar({"front", "backend", "instalador"}, "linux")

    # assert
    assert codigo == 7 and len(chamadas) == 1
    assert "Falhou no passo 'front'" in capsys.readouterr().err


def test_artefatos_de_build_nao_sao_versionados():
    # assert (AGENTS.md §4.1: dist/ e binários gerados não entram no git)
    gitignore = (RAIZ / ".gitignore").read_text(encoding="utf-8")

    assert "empacotamento/build/" in gitignore
    assert "empacotamento/dist/" in gitignore
    assert "empacotamento/instaladores/" in gitignore
