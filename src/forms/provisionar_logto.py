"""Provisiona o Logto como código (AGENTS.md §2.12, §4.1): roda em toda subida do compose e é
idempotente — o que já existe é atualizado, nunca duplicado.

O que configura: o API resource do app (token de acesso de 10 minutos), o aplicativo SPA do
front (refresh token com rotação), um aplicativo M2M só para a API (ler perfil e apagar conta),
o conector de e-mail (SMTP), e a experiência de login (e-mail e senha de no mínimo 10 caracteres,
tela em PT-BR, aceite dos termos no cadastro). No fim escreve, na pasta de configuração
compartilhada, o `api.env` (credenciais M2M, lido pela API) e o `frontend-config.json` (lido pelo
front em `/config.json`, quando algum servidor estático o serve).

Para chamar a Management API ele usa o aplicativo `m-default`, que o próprio Logto cria no seed;
o segredo dele é lido do banco do Logto. Esse segredo **não** vai para a API nem para o disco.
"""

import json
import os
import stat
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg

RECURSO_MANAGEMENT = "https://default.logto.app/api"
NOME_DO_APLICATIVO_WEB = "data-collect"
NOME_DO_APLICATIVO_API = "data-collect-api"
NOME_DO_RECURSO = "data-collect API"
NOME_DO_PAPEL_M2M = "Logto Management API access"
VIDA_DO_TOKEN_SEGUNDOS = 600  # 10 minutos (AGENTS.md §2.12)
VIDA_DO_REFRESH_EM_DIAS = 14
SENHA_MINIMA = 10
HOST_DO_TENANT_ADMIN = "localhost:3002"
CONECTOR_SMTP = "simple-mail-transfer-protocol"


class ProvisionamentoFalhou(RuntimeError):
    pass


@dataclass(frozen=True)
class Ambiente:
    logto_interno: str  # ex.: http://logto:3001
    logto_admin_interno: str  # ex.: http://logto:3002 (onde o `m-default` pede token)
    banco_do_logto: str
    recurso_da_api: str
    app_url: str
    auth_url: str
    origens_extras: tuple[str, ...]
    smtp_host: str
    smtp_porta: int
    smtp_usuario: str
    smtp_senha: str
    smtp_remetente: str
    pasta_de_configuracao: Path

    @classmethod
    def do_ambiente(cls, e: Mapping[str, str] | None = None) -> "Ambiente":
        e = os.environ if e is None else e
        interno = e.get("LOGTO_INTERNO", "http://logto:3001").rstrip("/")
        return cls(
            logto_interno=interno,
            logto_admin_interno=e.get("LOGTO_ADMIN_INTERNO", "http://logto:3002").rstrip("/"),
            banco_do_logto=_obrigatoria(e, "LOGTO_DB_URL"),
            recurso_da_api=_obrigatoria(e, "LOGTO_API_RESOURCE"),
            app_url=_obrigatoria(e, "APP_URL").rstrip("/"),
            auth_url=_obrigatoria(e, "AUTH_URL").rstrip("/"),
            origens_extras=tuple(
                o.strip().rstrip("/") for o in e.get("ORIGENS_EXTRAS", "").split(",") if o.strip()
            ),
            smtp_host=e.get("SMTP_HOST", "mailpit"),
            smtp_porta=int(e.get("SMTP_PORT", "1025")),
            smtp_usuario=e.get("SMTP_USER", ""),
            smtp_senha=e.get("SMTP_PASSWORD", ""),
            smtp_remetente=e.get("SMTP_FROM", "no-reply@data-collect.local"),
            pasta_de_configuracao=Path(e.get("FORMS_CONFIG_DIR", "/config")),
        )


def _obrigatoria(ambiente: Mapping[str, str], nome: str) -> str:
    valor = ambiente.get(nome, "").strip()
    if not valor:
        raise ProvisionamentoFalhou(f"Variável de ambiente obrigatória ausente: {nome}.")
    return valor


JsonObjeto = dict[str, object]


class ApiLogto:
    """Os poucos verbos da Management API que o provisionamento usa."""

    def __init__(self, base: str, token: str, http: httpx.Client) -> None:
        self._base = base
        self._http = http
        self._cabecalhos = {"Authorization": f"Bearer {token}"}

    def _chamar(self, metodo: str, caminho: str, corpo: object = None) -> object:
        resposta = self._http.request(
            metodo, f"{self._base}/api{caminho}", headers=self._cabecalhos, json=corpo
        )
        if resposta.status_code >= 400:
            # Sem o corpo da requisição no erro: pode conter segredo de SMTP.
            raise ProvisionamentoFalhou(
                f"Logto recusou {metodo} {caminho}: {resposta.status_code} {resposta.text[:300]}"
            )
        try:
            return resposta.json() if resposta.content else None
        except ValueError:
            return None  # algumas respostas de sucesso (ex.: 201 sem corpo) não são JSON

    def listar(self, caminho: str) -> list[JsonObjeto]:
        resultado = self._chamar("GET", caminho)
        return resultado if isinstance(resultado, list) else []

    def obter(self, caminho: str) -> JsonObjeto:
        resultado = self._chamar("GET", caminho)
        if not isinstance(resultado, dict):
            raise ProvisionamentoFalhou(f"Resposta inesperada em {caminho}.")
        return resultado

    def criar(self, caminho: str, corpo: object) -> JsonObjeto:
        resultado = self._chamar("POST", caminho, corpo)
        if not isinstance(resultado, dict):
            raise ProvisionamentoFalhou(f"Resposta inesperada ao criar em {caminho}.")
        return resultado

    def atualizar(self, caminho: str, corpo: object) -> JsonObjeto:
        resultado = self._chamar("PATCH", caminho, corpo)
        return resultado if isinstance(resultado, dict) else {}

    def enviar(self, caminho: str, corpo: object) -> None:
        self._chamar("POST", caminho, corpo)


def obter_token_de_gestao(ambiente: Ambiente, http: httpx.Client) -> str:
    """Token do `m-default` (aplicativo M2M do seed) para a Management API do tenant `default`."""
    with psycopg.connect(ambiente.banco_do_logto) as conexao:
        linha = conexao.execute(
            "SELECT secret FROM applications WHERE tenant_id = 'admin' AND id = 'm-default'"
        ).fetchone()
    if linha is None:
        raise ProvisionamentoFalhou("O seed do Logto ainda não criou o aplicativo m-default.")
    resposta = http.post(
        f"{ambiente.logto_admin_interno}/oidc/token",
        # O Logto escolhe o tenant (admin ou default) pelo host da requisição; `logto:3002` não é
        # um host que ele reconheça, `localhost:3002` é o do tenant admin.
        headers={"Host": HOST_DO_TENANT_ADMIN},
        auth=("m-default", str(linha[0])),
        data={"grant_type": "client_credentials", "resource": RECURSO_MANAGEMENT, "scope": "all"},
    )
    if resposta.status_code != 200:
        raise ProvisionamentoFalhou(f"Não obtive o token de gestão: {resposta.status_code}.")
    return str(resposta.json()["access_token"])


def _por_nome(itens: list[JsonObjeto], nome: str) -> JsonObjeto | None:
    return next((i for i in itens if i.get("name") == nome), None)


def garantir_recurso(api: ApiLogto, ambiente: Ambiente) -> str:
    existente = next(
        (r for r in api.listar("/resources") if r.get("indicator") == ambiente.recurso_da_api),
        None,
    )
    if existente is None:
        existente = api.criar(
            "/resources", {"name": NOME_DO_RECURSO, "indicator": ambiente.recurso_da_api}
        )
    api.atualizar(f"/resources/{existente['id']}", {"accessTokenTtl": VIDA_DO_TOKEN_SEGUNDOS})
    return str(existente["id"])


def _origens_do_front(ambiente: Ambiente) -> list[str]:
    return [ambiente.app_url, *ambiente.origens_extras]


def garantir_aplicativo_web(api: ApiLogto, ambiente: Ambiente) -> str:
    origens = _origens_do_front(ambiente)
    corpo: JsonObjeto = {
        "name": NOME_DO_APLICATIVO_WEB,
        "description": "Interface web do data-collect",
        "type": "SPA",
        "oidcClientMetadata": {
            "redirectUris": [f"{o}/callback" for o in origens],
            "postLogoutRedirectUris": [f"{o}/" for o in origens],
        },
        "customClientMetadata": {
            "corsAllowedOrigins": origens,
            "alwaysIssueRefreshToken": True,
            "rotateRefreshToken": True,
            "refreshTokenTtlInDays": VIDA_DO_REFRESH_EM_DIAS,
        },
    }
    existente = _por_nome(api.listar("/applications"), NOME_DO_APLICATIVO_WEB)
    if existente is None:
        return str(api.criar("/applications", corpo)["id"])
    atualizacao = {k: v for k, v in corpo.items() if k != "type"}
    api.atualizar(f"/applications/{existente['id']}", atualizacao)
    return str(existente["id"])


def garantir_aplicativo_m2m(api: ApiLogto) -> tuple[str, str]:
    """O aplicativo M2M da API, com o papel de acesso à Management API. Devolve (id, segredo)."""
    existente = _por_nome(api.listar("/applications"), NOME_DO_APLICATIVO_API)
    if existente is None:
        existente = api.criar(
            "/applications",
            {
                "name": NOME_DO_APLICATIVO_API,
                "description": "Lê o perfil de quem entra e apaga contas (LGPD)",
                "type": "MachineToMachine",
            },
        )
    id_do_aplicativo = str(existente["id"])
    papel = _por_nome(api.listar("/roles"), NOME_DO_PAPEL_M2M)
    if papel is None:
        raise ProvisionamentoFalhou(f"O papel '{NOME_DO_PAPEL_M2M}' não existe no Logto.")
    ja_tem = any(
        p.get("id") == papel["id"] for p in api.listar(f"/applications/{id_do_aplicativo}/roles")
    )
    if not ja_tem:
        api.enviar(f"/roles/{papel['id']}/applications", {"applicationIds": [id_do_aplicativo]})
    segredos = api.listar(f"/applications/{id_do_aplicativo}/secrets")
    if not segredos:
        raise ProvisionamentoFalhou("O aplicativo M2M da API ficou sem segredo no Logto.")
    return id_do_aplicativo, str(segredos[0]["value"])


def _modelos_de_email() -> list[JsonObjeto]:
    textos = {
        "Register": ("Confirme seu e-mail no data-collect", "criar sua conta"),
        "SignIn": ("Seu código de acesso ao data-collect", "entrar"),
        "ForgotPassword": ("Recuperação de senha do data-collect", "redefinir a sua senha"),
        "Generic": ("Seu código de verificação do data-collect", "continuar"),
    }
    return [
        {
            "usageType": uso,
            "contentType": "text/plain",
            "subject": assunto,
            "content": f"Seu código para {acao} é {{{{code}}}}. Ele vale por 10 minutos. "
            "Se não foi você, ignore esta mensagem.",
        }
        for uso, (assunto, acao) in textos.items()
    ]


def garantir_conector_de_email(api: ApiLogto, ambiente: Ambiente) -> None:
    autenticacao: JsonObjeto = {"type": "login", "user": ambiente.smtp_usuario or "-"}
    autenticacao["pass"] = ambiente.smtp_senha or "-"
    configuracao: JsonObjeto = {
        "host": ambiente.smtp_host,
        "port": ambiente.smtp_porta,
        "fromEmail": ambiente.smtp_remetente,
        "auth": autenticacao,
        "templates": _modelos_de_email(),
    }
    existente = next(
        (c for c in api.listar("/connectors") if c.get("connectorId") == CONECTOR_SMTP), None
    )
    if existente is None:
        api.criar("/connectors", {"connectorId": CONECTOR_SMTP, "config": configuracao})
    else:
        api.atualizar(f"/connectors/{existente['id']}", {"config": configuracao})


def configurar_login(api: ApiLogto, ambiente: Ambiente) -> None:
    api.atualizar(
        "/sign-in-exp",
        {
            "color": {
                "primaryColor": "#1D4ED8",
                "isDarkModeEnabled": False,
                "darkPrimaryColor": "#1D4ED8",
            },
            # Logo servido pelo próprio app: o padrão do Logto é uma imagem em logto.io, e nenhum
            # terceiro deve ver o IP de quem entra (AGENTS.md §2.15).
            "branding": {
                "logoUrl": f"{ambiente.app_url}/logo.svg",
                "darkLogoUrl": f"{ambiente.app_url}/logo.svg",
            },
            "languageInfo": {"autoDetect": False, "fallbackLanguage": "pt-BR"},
            "termsOfUseUrl": f"{ambiente.app_url}/#/termos",
            "privacyPolicyUrl": f"{ambiente.app_url}/#/privacidade",
            # Checkbox de aceite no cadastro (LGPD, §2.15); o registro do aceite é do app.
            "agreeToTermsPolicy": "ManualRegistrationOnly",
            "signUp": {"identifiers": ["email"], "password": True, "verify": True},
            "signIn": {
                "methods": [
                    {
                        "identifier": "email",
                        "password": True,
                        "verificationCode": False,
                        "isPasswordPrimary": True,
                    }
                ]
            },
            "passwordPolicy": {"length": {"min": SENHA_MINIMA, "max": 256}},
            "forgotPasswordMethods": ["EmailVerificationCode"],
        },
    )


def escrever_configuracao(ambiente: Ambiente, id_web: str, id_m2m: str, segredo_m2m: str) -> None:
    pasta = ambiente.pasta_de_configuracao
    pasta.mkdir(parents=True, exist_ok=True)
    api_env = pasta / "api.env"
    api_env.write_text(f"LOGTO_M2M_ID={id_m2m}\nLOGTO_M2M_SECRET={segredo_m2m}\n")
    # Só o dono lê: o segredo M2M vale como senha da Management API.
    api_env.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
    publica = {
        "logto": {
            "endpoint": ambiente.auth_url,
            "appId": id_web,
            "resource": ambiente.recurso_da_api,
        },
        "apiBase": ambiente.recurso_da_api,
    }
    (pasta / "frontend-config.json").write_text(json.dumps(publica, indent=2) + "\n")


def provisionar(ambiente: Ambiente, http: httpx.Client) -> None:
    token = obter_token_de_gestao(ambiente, http)
    api = ApiLogto(ambiente.logto_interno, token, http)
    garantir_recurso(api, ambiente)
    id_web = garantir_aplicativo_web(api, ambiente)
    id_m2m, segredo_m2m = garantir_aplicativo_m2m(api)
    garantir_conector_de_email(api, ambiente)
    configurar_login(api, ambiente)
    escrever_configuracao(ambiente, id_web, id_m2m, segredo_m2m)


def main() -> int:
    ambiente = Ambiente.do_ambiente()
    ultima_falha = ""
    # O Logto leva alguns segundos para aceitar chamadas depois do seed.
    for tentativa in range(1, 11):
        try:
            with httpx.Client(timeout=10.0) as http:
                provisionar(ambiente, http)
            print("Logto provisionado.")
            return 0
        except (ProvisionamentoFalhou, httpx.HTTPError, psycopg.Error, KeyError) as erro:
            ultima_falha = str(erro)
            print(f"Tentativa {tentativa}/10 falhou: {ultima_falha}", file=sys.stderr)
            time.sleep(3)
    print(f"Provisionamento do Logto falhou: {ultima_falha}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
