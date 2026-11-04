"""Segredos: hash de token e cifra de chave (AGENTS.md §12). Único lugar com criptografia.

O que só se confere (token de convite) é guardado como **hash**; o que precisa ser reutilizado
(chave de API do LLM) é **cifrado**, com a chave-mestra só no ambiente. Senha é do Logto.
"""

import hashlib
import hmac
import secrets
from collections.abc import Mapping, Sequence

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from forms.models import ErroDeDominio

VARIAVEL_DA_CHAVE_MESTRA = "FORMS_CHAVE_MESTRA"


class SegredoIndisponivel(ErroDeDominio):
    """Sem chave-mestra, ou texto cifrado com outra chave: nada de segredo pode ser lido."""


def novo_token() -> str:
    """256 bits aleatórios, URL-safe: o token que vai no link do convite."""
    return secrets.token_urlsafe(32)


def hash_do_token(token: str) -> str:
    """SHA-256 em hexadecimal. Token de 256 bits já é aleatório demais para precisar de sal."""
    return hashlib.sha256(token.encode()).hexdigest()


def iguais(a: str, b: str) -> bool:
    """Comparação em tempo constante."""
    return hmac.compare_digest(a.encode(), b.encode())


def nova_chave_mestra() -> str:
    return Fernet.generate_key().decode()


class Cifra:
    """Fernet com suporte a rotação: a primeira chave cifra, todas as chaves decifram."""

    def __init__(self, chaves: Sequence[str]) -> None:
        if not chaves:
            raise SegredoIndisponivel("Nenhuma chave-mestra configurada.")
        try:
            self._fernet = MultiFernet([Fernet(c.encode()) for c in chaves])
        except ValueError as erro:
            raise SegredoIndisponivel("A chave-mestra é inválida (use uma chave Fernet).") from erro

    def cifrar(self, texto: str) -> str:
        return self._fernet.encrypt(texto.encode()).decode()

    def decifrar(self, cifrado: str) -> str:
        try:
            return self._fernet.decrypt(cifrado.encode()).decode()
        except InvalidToken as erro:
            raise SegredoIndisponivel(
                "Não foi possível decifrar (chave-mestra trocada?)."
            ) from erro

    def __repr__(self) -> str:
        return "Cifra(<chaves ocultas>)"


def cifra_do_ambiente(ambiente: Mapping[str, str]) -> Cifra | None:
    """`FORMS_CHAVE_MESTRA` aceita várias chaves separadas por vírgula (a primeira cifra)."""
    bruto = (ambiente.get(VARIAVEL_DA_CHAVE_MESTRA) or "").strip()
    chaves = [c.strip() for c in bruto.split(",") if c.strip()]
    return Cifra(chaves) if chaves else None
