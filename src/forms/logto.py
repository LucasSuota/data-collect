"""Cliente mínimo da Management API do Logto (AGENTS.md §2.12, §2.15).

Só o que o app precisa: ler o perfil de quem entrou (o token de acesso não traz nome nem e-mail)
e apagar a conta quando a pessoa pede a exclusão. Autentica como aplicativo M2M (client
credentials); o segredo vem do ambiente e nunca aparece em log nem em `repr`.
"""

from typing import Protocol

import httpx

from forms.models import ErroDeDominio


class IdentidadeIndisponivel(ErroDeDominio):
    """O Logto não respondeu como esperado (fora do ar, M2M inválido ou usuário inexistente)."""


class GestorDeIdentidade(Protocol):
    def perfil(self, sub: str) -> tuple[str | None, str | None]:
        """(nome, e-mail) da pessoa, se o Logto os conhece."""
        ...

    def apagar(self, sub: str) -> None:
        """Remove a conta no Logto. Conta que já não existe conta como removida."""
        ...


class ClienteLogto:
    def __init__(
        self,
        endpoint: str,
        id_do_aplicativo: str,
        segredo: str,
        *,
        cliente_http: httpx.Client | None = None,
    ) -> None:
        self._base = endpoint.rstrip("/")
        self._id = id_do_aplicativo
        self._segredo = segredo
        self._http = cliente_http or httpx.Client(timeout=5.0)

    def __repr__(self) -> str:
        return f"ClienteLogto(endpoint={self._base!r})"  # sem o segredo

    def _token(self) -> str:
        try:
            resposta = self._http.post(
                f"{self._base}/oidc/token",
                data={
                    "grant_type": "client_credentials",
                    "resource": "https://default.logto.app/api",
                    "scope": "all",
                },
                auth=(self._id, self._segredo),
            )
            resposta.raise_for_status()
            return str(resposta.json()["access_token"])
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            raise IdentidadeIndisponivel(
                "Não foi possível falar com o serviço de login agora."
            ) from erro

    def perfil(self, sub: str) -> tuple[str | None, str | None]:
        try:
            resposta = self._http.get(
                f"{self._base}/api/users/{sub}",
                headers={"Authorization": f"Bearer {self._token()}"},
            )
            if resposta.status_code == 404:
                return None, None
            resposta.raise_for_status()
            dados = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise IdentidadeIndisponivel(
                "Não foi possível falar com o serviço de login agora."
            ) from erro
        return dados.get("name") or dados.get("username"), dados.get("primaryEmail")

    def apagar(self, sub: str) -> None:
        try:
            resposta = self._http.delete(
                f"{self._base}/api/users/{sub}",
                headers={"Authorization": f"Bearer {self._token()}"},
            )
            if resposta.status_code not in (200, 204, 404):
                resposta.raise_for_status()
        except httpx.HTTPError as erro:
            raise IdentidadeIndisponivel(
                "Os dados foram removidos, mas não foi possível apagar a conta de login. "
                "Tente de novo."
            ) from erro
