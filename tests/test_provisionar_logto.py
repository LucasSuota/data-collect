"""Provisionamento do Logto (AGENTS.md §4.1) contra um Logto falso em memória: o que importa é
ser idempotente e escrever a configuração certa; o teste contra o Logto real foi manual."""

import json
from pathlib import Path

import httpx
import pytest

from forms.infra.provisionar_logto import (
    Ambiente,
    ApiLogto,
    ProvisionamentoFalhou,
    configurar_login,
    escrever_configuracao,
    garantir_aplicativo_m2m,
    garantir_aplicativo_web,
    garantir_recurso,
)


class LogtoFalso:
    def __init__(self) -> None:
        self.recursos: list[dict] = []
        self.aplicativos: list[dict] = []
        self.papeis = [{"id": "papel1", "name": "Logto Management API access"}]
        self.papeis_dos_aplicativos: dict[str, list[str]] = {}
        self.login: dict = {}
        self.chamadas: list[tuple[str, str]] = []

    def __call__(self, requisicao: httpx.Request) -> httpx.Response:
        caminho = requisicao.url.path.removeprefix("/api")
        metodo = requisicao.method
        corpo = json.loads(requisicao.content) if requisicao.content else None
        self.chamadas.append((metodo, caminho))
        if caminho == "/resources" and metodo == "GET":
            return httpx.Response(200, json=self.recursos)
        if caminho == "/resources" and metodo == "POST":
            recurso = {"id": f"r{len(self.recursos)}", **corpo}
            self.recursos.append(recurso)
            return httpx.Response(201, json=recurso)
        if caminho.startswith("/resources/") and metodo == "PATCH":
            recurso = next(r for r in self.recursos if caminho.endswith(r["id"]))
            recurso.update(corpo)
            return httpx.Response(200, json=recurso)
        if caminho == "/applications" and metodo == "GET":
            return httpx.Response(200, json=self.aplicativos)
        if caminho == "/applications" and metodo == "POST":
            app = {"id": f"a{len(self.aplicativos)}", **corpo}
            self.aplicativos.append(app)
            return httpx.Response(201, json=app)
        if caminho.startswith("/applications/") and caminho.endswith("/roles"):
            id_app = caminho.split("/")[2]
            ids = self.papeis_dos_aplicativos.get(id_app, [])
            return httpx.Response(200, json=[{"id": i} for i in ids])
        if caminho.startswith("/applications/") and caminho.endswith("/secrets"):
            return httpx.Response(200, json=[{"name": "Default secret", "value": "segredo-m2m"}])
        if caminho.startswith("/applications/") and metodo == "PATCH":
            app = next(a for a in self.aplicativos if caminho.endswith(a["id"]))
            app.update(corpo)
            return httpx.Response(200, json=app)
        if caminho == "/roles":
            return httpx.Response(200, json=self.papeis)
        if caminho.startswith("/roles/") and caminho.endswith("/applications"):
            for id_app in corpo["applicationIds"]:
                self.papeis_dos_aplicativos.setdefault(id_app, []).append(caminho.split("/")[2])
            return httpx.Response(201)
        if caminho == "/sign-in-exp" and metodo == "PATCH":
            self.login.update(corpo)
            return httpx.Response(200, json=self.login)
        return httpx.Response(404, json={"code": "nao_previsto", "path": caminho})


@pytest.fixture
def logto() -> LogtoFalso:
    return LogtoFalso()


@pytest.fixture
def api(logto: LogtoFalso) -> ApiLogto:
    return ApiLogto("http://logto", "token", httpx.Client(transport=httpx.MockTransport(logto)))


@pytest.fixture
def ambiente(tmp_path: Path) -> Ambiente:
    return Ambiente.do_ambiente(
        {
            "LOGTO_DB_URL": "postgresql://x",
            "LOGTO_API_RESOURCE": "https://app.exemplo/api",
            "APP_URL": "https://app.exemplo",
            "AUTH_URL": "https://auth.exemplo",
            "ORIGENS_EXTRAS": "http://localhost:5173",
            "FORMS_CONFIG_DIR": str(tmp_path),
        }
    )


def test_recurso_da_api_e_criado_uma_vez_com_token_de_10_minutos(api, logto, ambiente) -> None:
    garantir_recurso(api, ambiente)
    garantir_recurso(api, ambiente)

    assert len(logto.recursos) == 1
    assert logto.recursos[0]["accessTokenTtl"] == 600


def test_aplicativo_web_rota_o_refresh_e_libera_so_as_origens_do_front(
    api, logto, ambiente
) -> None:
    garantir_aplicativo_web(api, ambiente)
    garantir_aplicativo_web(api, ambiente)

    assert len(logto.aplicativos) == 1
    app = logto.aplicativos[0]
    assert app["customClientMetadata"]["rotateRefreshToken"] is True
    assert app["customClientMetadata"]["corsAllowedOrigins"] == [
        "https://app.exemplo",
        "http://localhost:5173",
    ]
    assert app["oidcClientMetadata"]["redirectUris"] == [
        "https://app.exemplo/callback",
        "http://localhost:5173/callback",
    ]


def test_aplicativo_m2m_recebe_o_papel_uma_so_vez(api, logto) -> None:
    id_um, segredo = garantir_aplicativo_m2m(api)
    id_dois, _ = garantir_aplicativo_m2m(api)

    assert id_um == id_dois
    assert segredo == "segredo-m2m"
    assert logto.papeis_dos_aplicativos[id_um] == ["papel1"]


def test_aplicativo_m2m_falha_claro_sem_o_papel_de_gestao(api, logto) -> None:
    logto.papeis = []

    with pytest.raises(ProvisionamentoFalhou, match="papel"):
        garantir_aplicativo_m2m(api)


def test_login_exige_email_e_senha_de_10_caracteres_em_portugues(api, logto, ambiente) -> None:
    configurar_login(api, ambiente)

    assert logto.login["signUp"]["identifiers"] == ["email"]
    assert logto.login["passwordPolicy"]["length"]["min"] == 10
    assert logto.login["languageInfo"]["fallbackLanguage"] == "pt-BR"
    assert logto.login["agreeToTermsPolicy"] == "ManualRegistrationOnly"
    assert logto.login["branding"]["logoUrl"].startswith("https://app.exemplo/")


def test_configuracao_escrita_nao_mistura_segredo_com_o_arquivo_publico(ambiente) -> None:
    escrever_configuracao(ambiente, "id-web", "id-m2m", "segredo-m2m")

    publico = (ambiente.pasta_de_configuracao / "frontend-config.json").read_text()
    privado = (ambiente.pasta_de_configuracao / "api.env").read_text()
    assert "segredo-m2m" not in publico
    assert json.loads(publico)["logto"]["appId"] == "id-web"
    assert "LOGTO_M2M_SECRET=segredo-m2m" in privado


def test_configuracao_publica_aponta_o_front_para_a_api_direto(ambiente) -> None:
    # Sem proxy na frente, o front não tem um `/api` na própria origem: fala com a API pelo
    # endereço dela, que é o mesmo do API resource.
    escrever_configuracao(ambiente, "id-web", "id-m2m", "segredo-m2m")

    publico = json.loads((ambiente.pasta_de_configuracao / "frontend-config.json").read_text())
    assert publico["apiBase"] == "https://app.exemplo/api"


def test_variavel_obrigatoria_ausente_e_erro_claro() -> None:
    with pytest.raises(ProvisionamentoFalhou, match="LOGTO_DB_URL"):
        Ambiente.do_ambiente({})
