import io
import json
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from forms import app as aplicacao
from forms.api import Configuracao, criar_app

TOKEN = "token-de-teste"


@pytest.fixture
def front(tmp_path: Path) -> Path:
    pasta = tmp_path / "front"
    (pasta / "assets").mkdir(parents=True)
    (pasta / "index.html").write_text("<html><title>Construtor</title><div id='raiz'></div></html>")
    (pasta / "assets" / "app.js").write_text("console.log('ok')")
    return pasta


@pytest.fixture
def cliente(tmp_path: Path, front: Path) -> TestClient:
    configuracao = Configuracao(
        banco=tmp_path / "dados" / "forms.db",
        pasta_de_dados=tmp_path / "dados",
        token=TOKEN,
        dispensar_token=False,
        origens_cors=("http://localhost:5173",),
    )
    return TestClient(criar_app(configuracao, pasta_do_front=front))


# --- front na mesma origem ---


def test_serve_o_index_na_raiz_sem_exigir_token(cliente):
    # act: o navegador carrega a página sem poder mandar o cabeçalho
    resposta = cliente.get("/")

    # assert
    assert resposta.status_code == 200 and "Construtor" in resposta.text
    assert resposta.headers["content-type"].startswith("text/html")


def test_serve_os_arquivos_estaticos_sem_token(cliente):
    # act
    resposta = cliente.get("/assets/app.js")

    # assert
    assert resposta.status_code == 200 and "console.log" in resposta.text


def test_a_api_continua_exigindo_o_token_mesmo_com_o_front_montado(cliente):
    # act
    sem = cliente.get("/formularios")
    com = cliente.get("/formularios", headers={"X-Forms-Token": TOKEN})

    # assert
    assert sem.status_code == 401
    assert com.status_code == 200 and com.json() == []


@pytest.mark.parametrize(
    "caminho", ["/catalogo", "/registros/1", "/anexos/1", "/openapi.json", "/docs"]
)
def test_toda_rota_da_api_e_a_documentacao_exigem_token(cliente, caminho):
    # act / assert: o front estático não pode virar uma brecha na API
    assert cliente.get(caminho).status_code == 401


def test_api_de_escrita_tambem_exige_token(cliente):
    # act
    resposta = cliente.post("/formularios", json={"nome": "x", "definicao": {"campos": []}})

    # assert
    assert resposta.status_code == 401


def test_arquivo_estatico_inexistente_e_404_no_formato_uniforme(cliente):
    # act
    resposta = cliente.get("/assets/nao-existe.js")

    # assert
    assert resposta.status_code == 404
    assert set(resposta.json()) == {"detalhe", "erros"}


def test_nao_deixa_ler_arquivo_fora_da_pasta_do_front(cliente, tmp_path):
    # arrange
    (tmp_path / "segredo.txt").write_text("segredo")

    # act
    resposta = cliente.get("/../segredo.txt")
    codificada = cliente.get("/%2e%2e/segredo.txt")

    # assert
    assert "segredo" not in resposta.text and "segredo" not in codificada.text


def test_sem_pasta_do_front_a_raiz_e_404_e_a_api_segue_igual(tmp_path):
    # arrange
    configuracao = Configuracao(
        tmp_path / "f.db", tmp_path, TOKEN, False, ("http://localhost:5173",)
    )
    cliente = TestClient(criar_app(configuracao), headers={"X-Forms-Token": TOKEN})

    # act / assert
    assert cliente.get("/").status_code == 404
    assert cliente.get("/formularios").status_code == 200


# --- configuração do app instalado ---


def test_dados_ficam_na_pasta_de_dados_do_sistema_e_nunca_dentro_do_pacote(tmp_path):
    # act
    configuracao = aplicacao.configuracao_do_app(
        {"FORMS_TOKEN": "t"}, pasta_do_usuario=tmp_path / "usuario"
    )

    # assert
    assert configuracao.pasta_de_dados == tmp_path / "usuario"
    assert configuracao.banco == tmp_path / "usuario" / "forms.db"
    pacote = Path(aplicacao.__file__).resolve().parent
    assert not configuracao.pasta_de_dados.resolve().is_relative_to(pacote)


def test_pasta_de_dados_padrao_vem_do_platformdirs():
    # act
    configuracao = aplicacao.configuracao_do_app({"FORMS_TOKEN": "t"})

    # assert
    import platformdirs

    assert configuracao.pasta_de_dados == Path(
        platformdirs.user_data_dir(aplicacao.NOME_DO_APP, appauthor=False)
    )


def test_variavel_de_ambiente_sobrescreve_a_pasta_de_dados(tmp_path):
    # act
    configuracao = aplicacao.configuracao_do_app(
        {"FORMS_TOKEN": "t", "FORMS_DATA_DIR": str(tmp_path / "x")}
    )

    # assert
    assert configuracao.pasta_de_dados == tmp_path / "x"
    assert configuracao.banco == tmp_path / "x" / "forms.db"


def test_o_token_vem_do_ambiente_e_o_cors_nao_importa_na_mesma_origem():
    # act
    configuracao = aplicacao.configuracao_do_app({"FORMS_TOKEN": "do-electron"})

    # assert
    assert configuracao.token == "do-electron" and configuracao.dispensar_token is False


def test_sem_token_o_app_nao_sobe():
    # act / assert: falha fechada, igual à API
    with pytest.raises(aplicacao.TokenAusente):
        aplicacao.configuracao_do_app({})


def test_token_vazio_tambem_nao_sobe():
    with pytest.raises(aplicacao.TokenAusente):
        aplicacao.configuracao_do_app({"FORMS_TOKEN": "   "})


def test_o_app_instalado_nunca_dispensa_o_token_mesmo_se_a_variavel_de_dev_estiver_ligada():
    # act
    configuracao = aplicacao.configuracao_do_app({"FORMS_TOKEN": "t", "FORMS_SKIP_TOKEN": "1"})

    # assert
    assert configuracao.dispensar_token is False


# --- localizar o front ---


def test_localiza_o_front_pela_variavel_de_ambiente(front):
    # act / assert
    assert aplicacao.localizar_front({"FORMS_FRONTEND_DIST": str(front)}) == front


def test_localiza_o_front_dentro_do_executavel_empacotado(tmp_path):
    # arrange: o PyInstaller descompacta os dados em sys._MEIPASS
    (tmp_path / "frontend_dist").mkdir()
    (tmp_path / "frontend_dist" / "index.html").write_text("x")

    # act
    achado = aplicacao.localizar_front({}, empacotado=True, base_do_executavel=tmp_path)

    # assert
    assert achado == tmp_path / "frontend_dist"


def test_sem_o_build_do_front_devolve_none_em_vez_de_quebrar(tmp_path):
    # act / assert
    assert aplicacao.localizar_front({"FORMS_FRONTEND_DIST": str(tmp_path / "nada")}) is None


# --- porta livre e primeira linha ---


def test_escolhe_uma_porta_livre_so_em_127_0_0_1():
    # act
    soquete = aplicacao.abrir_soquete_local()

    # assert
    try:
        endereco, porta = soquete.getsockname()
        assert endereco == "127.0.0.1" and porta > 0
    finally:
        soquete.close()


def test_duas_execucoes_recebem_portas_diferentes():
    # act
    a, b = aplicacao.abrir_soquete_local(), aplicacao.abrir_soquete_local()

    # assert
    try:
        assert a.getsockname()[1] != b.getsockname()[1]
    finally:
        a.close()
        b.close()


def test_o_soquete_ja_esta_escutando_e_aceita_conexao_antes_do_servidor_aceitar():
    # arrange: a porta é do soquete que o uvicorn vai receber: ninguém a rouba no intervalo
    soquete = aplicacao.abrir_soquete_local()
    porta = soquete.getsockname()[1]

    # act
    try:
        cliente = socket.create_connection(("127.0.0.1", porta), timeout=2)
        cliente.close()
    finally:
        soquete.close()


def test_a_primeira_linha_e_um_json_com_a_porta():
    # act
    linha = aplicacao.primeira_linha(51234)

    # assert
    assert json.loads(linha) == {"porta": 51234}
    assert "\n" not in linha


def test_main_imprime_a_porta_como_primeira_linha_e_entrega_o_soquete_ao_servidor(tmp_path, front):
    # arrange
    saida = io.StringIO()
    chamadas = []

    def servidor_falso(app, soquete):
        chamadas.append((app, soquete.getsockname()))

    ambiente = {
        "FORMS_TOKEN": "t",
        "FORMS_DATA_DIR": str(tmp_path / "dados"),
        "FORMS_FRONTEND_DIST": str(front),
    }

    # act
    codigo = aplicacao.main(ambiente, saida=saida, servir=servidor_falso)

    # assert
    primeira, *resto = saida.getvalue().splitlines()
    assert codigo == 0 and resto == []
    (app, (endereco, porta)) = chamadas[0]
    assert json.loads(primeira) == {"porta": porta} and endereco == "127.0.0.1"
    assert TestClient(app).get("/").status_code == 200  # o front montado


def test_main_sem_token_nao_imprime_porta_e_sai_com_erro_em_portugues(capsys):
    # arrange
    saida = io.StringIO()

    # act
    codigo = aplicacao.main({}, saida=saida, servir=lambda *a: None)

    # assert
    assert codigo == 2 and saida.getvalue() == ""
    assert "FORMS_TOKEN" in capsys.readouterr().err


def test_main_cria_a_pasta_de_dados_e_nao_escreve_nada_fora_dela(tmp_path):
    # arrange
    pasta = tmp_path / "usuario" / "dados"

    # act
    aplicacao.main(
        {"FORMS_TOKEN": "t", "FORMS_DATA_DIR": str(pasta)},
        saida=io.StringIO(),
        servir=lambda *a: None,
    )

    # assert
    assert pasta.is_dir()


def test_main_servindo_de_verdade_responde_pela_porta_anunciada(tmp_path, front):
    # arrange: servidor real numa thread, como o Electron o usaria
    import threading
    import time
    import urllib.request

    saida = io.StringIO()
    parar = threading.Event()
    servidores = []

    def servir(app, soquete):
        import uvicorn

        servidor = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        servidores.append(servidor)
        servidor.run(sockets=[soquete])

    ambiente = {
        "FORMS_TOKEN": "segredo",
        "FORMS_DATA_DIR": str(tmp_path / "d"),
        "FORMS_FRONTEND_DIST": str(front),
    }
    fio = threading.Thread(
        target=lambda: aplicacao.main(ambiente, saida=saida, servir=servir), daemon=True
    )
    fio.start()

    # act
    try:
        for _ in range(100):
            if saida.getvalue() and servidores and servidores[0].started:
                break
            time.sleep(0.05)
        porta = json.loads(saida.getvalue().splitlines()[0])["porta"]
        pagina = urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=3).read().decode()
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{porta}/formularios", headers={"X-Forms-Token": "segredo"}
        )
        formularios = urllib.request.urlopen(pedido, timeout=3).read().decode()
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{porta}/formularios", timeout=3)
            sem_token = 200
        except urllib.error.HTTPError as erro:
            sem_token = erro.code
    finally:
        servidores[0].should_exit = True
        fio.join(timeout=5)
        parar.set()

    # assert
    assert "Construtor" in pagina and formularios == "[]" and sem_token == 401
