"""Validação do token de acesso do Logto (AGENTS.md §2.12 e §12).

A API confere a assinatura (JWKS do OIDC, com cache e rotação), o emissor (`iss`), o público
(`aud`, o API resource do app) e a validade (`exp`, com uma folga curta de relógio). O token dura
10 minutos; o SDK do front o renova com o refresh token. **Cargo e permissões não vêm do
token**: o servidor os lê do banco a cada requisição.
"""

from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from forms.models import NaoAutenticado

# Allowlist explícita: nunca "none" nem algoritmos simétricos (o Logto assina com chave
# assimétrica; aceitar HS256 com a chave pública abriria a falsificação por confusão de algoritmo).
ALGORITMOS_ACEITOS = ("ES384", "ES256", "ES512", "RS256", "RS384", "RS512", "PS256", "PS384")
FOLGA_DE_RELOGIO_SEGUNDOS = 30


@dataclass(frozen=True)
class Identidade:
    """Quem fez a chamada, segundo o token. Nome e e-mail podem faltar (token de API)."""

    sub: str
    nome: str | None = None
    email: str | None = None


class FonteDeChaves(Protocol):
    def chave_de(self, token: str) -> Any:
        """A chave pública que assinou o token, ou levanta `jwt.PyJWTError`."""
        ...


class JwksRemoto:
    """Busca as chaves no endpoint `jwks_uri` do Logto (descoberto no OIDC) e as guarda em cache."""

    def __init__(self, jwks_uri: str) -> None:
        self._cliente = PyJWKClient(jwks_uri, cache_keys=True, lifespan=3600, timeout=5)

    def chave_de(self, token: str) -> Any:
        return self._cliente.get_signing_key_from_jwt(token).key


class ChaveFixa:
    """Uma chave conhecida: os testes assinam com chaves geradas no próprio teste."""

    def __init__(self, chave: Any) -> None:
        self._chave = chave

    def chave_de(self, token: str) -> Any:
        return self._chave


class ValidadorDeToken:
    def __init__(self, emissor: str, audiencia: str, fonte: FonteDeChaves) -> None:
        self._emissor = emissor
        self._audiencia = audiencia
        self._fonte = fonte

    def validar(self, token: str) -> Identidade:
        if not token:
            raise NaoAutenticado("Token ausente.", "token_ausente")
        try:
            chave = self._fonte.chave_de(token)
            declaracoes = jwt.decode(
                token,
                chave,
                algorithms=list(ALGORITMOS_ACEITOS),
                audience=self._audiencia,
                issuer=self._emissor,
                leeway=FOLGA_DE_RELOGIO_SEGUNDOS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as erro:
            raise NaoAutenticado("Sua sessão expirou.", "token_expirado") from erro
        except jwt.PyJWTError as erro:
            # Mesma mensagem para tudo o mais: não ensina nada a quem tenta adivinhar.
            raise NaoAutenticado("Token inválido.", "token_invalido") from erro
        return Identidade(
            sub=str(declaracoes["sub"]),
            nome=_texto(declaracoes.get("name")),
            email=_texto(declaracoes.get("email")),
        )


def _texto(valor: object) -> str | None:
    return valor if isinstance(valor, str) and valor.strip() else None


def validador_do_ambiente(
    endpoint: str, audiencia: str, endpoint_interno: str | None = None
) -> ValidadorDeToken:
    """`endpoint` é o público do Logto (ex.: `https://auth.exemplo`), que vai no `iss` do token; o
    OIDC fica em `/oidc`. No compose as chaves (JWKS) são buscadas pela rede interna
    (`endpoint_interno`), sem passar pelo endereço público."""
    base = endpoint.rstrip("/")
    base_das_chaves = (endpoint_interno or endpoint).rstrip("/")
    return ValidadorDeToken(f"{base}/oidc", audiencia, JwksRemoto(f"{base_das_chaves}/oidc/jwks"))
