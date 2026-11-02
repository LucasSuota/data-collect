"""O único ponto que fala com o LLM (AGENTS.md §2.5, §3.3 e §12).

Todo o resto depende da interface `ClienteDeLLM`. O SDK é importado só aqui e só na hora de
usar, então o app sobe e funciona sem ele e sem chave. A chave vem só do ambiente (`.env`) e
nunca aparece em log, em `repr` nem em mensagem de erro.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol

from forms.models import ErroDeDominio

MODELO_PADRAO = "claude-sonnet-5-5"
VARIAVEL_DA_CHAVE = "ANTHROPIC_API_KEY"
VARIAVEL_DO_MODELO = "FORMS_LLM_MODELO"


class IaIndisponivel(ErroDeDominio):
    """Sem chave, sem internet ou sem o SDK: a IA não responde. O resto do app segue normal."""


class ClienteDeLLM(Protocol):
    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        """Devolve o texto da resposta. Levanta `IaIndisponivel` se não for possível responder."""
        ...

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        """Embeddings, quando houver provedor; senão levanta `IaIndisponivel`."""
        ...


class ClienteAnthropic:
    def __init__(self, chave: str, modelo: str) -> None:
        self._chave = chave
        self.modelo = modelo

    def __repr__(self) -> str:
        return f"ClienteAnthropic(modelo={self.modelo!r})"  # sem a chave

    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        try:
            import anthropic  # o único lugar do projeto que importa o SDK
        except ImportError as erro:
            raise IaIndisponivel(
                "A biblioteca da IA não está instalada. Instale com: uv sync --extra ia"
            ) from erro

        try:
            cliente = anthropic.Anthropic(api_key=self._chave)
            resposta = cliente.messages.create(
                model=self.modelo,
                max_tokens=maximo_de_tokens,
                system=sistema,
                messages=[{"role": "user", "content": mensagem}],
            )
        except (
            anthropic.APIConnectionError,
            anthropic.AuthenticationError,
            anthropic.RateLimitError,
            anthropic.APIStatusError,
        ) as erro:
            # A causa técnica fica encadeada para depuração, mas a mensagem é para a pessoa.
            raise IaIndisponivel(
                "Não foi possível consultar a IA agora (sem internet, chave inválida ou limite "
                "de uso). O restante do aplicativo continua funcionando."
            ) from erro
        return "".join(bloco.text for bloco in resposta.content if bloco.type == "text")

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        raise IaIndisponivel("Não há provedor de embeddings configurado; a busca usa só o BM25.")


class ClienteFalso:
    """Para os testes: respostas combinadas de antemão, e nenhuma chamada de rede."""

    def __init__(
        self,
        respostas: Sequence[str | Exception],
        vetores: Mapping[str, list[float]] | None = None,
    ) -> None:
        self._respostas = list(respostas)
        self._vetores = vetores
        self.chamadas: list[tuple[str, str]] = []

    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        self.chamadas.append((sistema, mensagem))
        assert self._respostas, "ClienteFalso sem resposta combinada para esta chamada"
        resposta = self._respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        if self._vetores is None:
            raise IaIndisponivel("Não há provedor de embeddings configurado.")
        return [self._vetores[texto] for texto in textos]


def criar_cliente(ambiente: Mapping[str, str]) -> ClienteDeLLM:
    chave = (ambiente.get(VARIAVEL_DA_CHAVE) or "").strip()
    if not chave:
        raise IaIndisponivel(
            f"A IA está indisponível: defina {VARIAVEL_DA_CHAVE} no .env. "
            "O restante do aplicativo continua funcionando."
        )
    return ClienteAnthropic(chave, ambiente.get(VARIAVEL_DO_MODELO) or MODELO_PADRAO)
