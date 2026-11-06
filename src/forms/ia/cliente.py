"""O único ponto que fala com o LLM (AGENTS.md §2.5, §3.3 e §12).

Todo o resto depende da interface `ProvedorDeLLM` (`ClienteDeLLM` é o mesmo nome, de antes):
trocar de provedor é trocar o adaptador. Há três: **Anthropic** (SDK, importado só aqui e só na
hora de usar), qualquer API **compatível com OpenAI** (OpenAI, Azure, Ollama, LM Studio, vLLM,
OpenRouter, Groq, Gemini no endpoint compatível), via `httpx`, e um **cliente falso** para os
testes. A chave nunca aparece em log, em `repr` nem em mensagem de erro.
"""

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from forms.dominio.models import ErroDeDominio

MODELO_PADRAO = "claude-sonnet-5-5"
VARIAVEL_DA_CHAVE = "ANTHROPIC_API_KEY"
VARIAVEL_DO_MODELO = "FORMS_LLM_MODELO"


class IaIndisponivel(ErroDeDominio):
    """Sem chave, sem internet ou sem o SDK: a IA não responde. O resto do app segue normal."""


@dataclass(frozen=True)
class Capacidades:
    """O que o provedor sabe fazer. Saída estruturada e escolha de ferramenta usam sempre o
    caminho portátil (prompt + JSON validado, §2.5), então não dependem destes campos."""

    embeddings: bool = False
    streaming: bool = False


class ProvedorDeLLM(Protocol):
    # Identifica o espaço dos vetores: vetores de modelos diferentes não se comparam. `None`
    # quando não há provedor de embeddings.
    modelo_de_vetores: str | None
    capacidades: Capacidades

    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        """Devolve o texto da resposta. Levanta `IaIndisponivel` se não for possível responder."""
        ...

    def completar_em_fluxo(
        self, sistema: str, mensagem: str, *, maximo_de_tokens: int
    ) -> Iterator[str]:
        """Pedaços da resposta, na ordem. Provedor sem streaming devolve tudo de uma vez."""
        ...

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        """Embeddings, quando houver provedor; senão levanta `IaIndisponivel`."""
        ...


ClienteDeLLM = ProvedorDeLLM  # nome antigo, ainda usado por `gerador.py`, `resumo.py` e `rag/`


class ClienteAnthropic:
    # A Anthropic não oferece embeddings: aqui a busca semântica fica desligada e vale o BM25.
    modelo_de_vetores: str | None = None
    capacidades = Capacidades(embeddings=False, streaming=True)

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

    def completar_em_fluxo(
        self, sistema: str, mensagem: str, *, maximo_de_tokens: int
    ) -> Iterator[str]:
        try:
            import anthropic  # o único lugar do projeto que importa o SDK
        except ImportError as erro:
            raise IaIndisponivel(
                "A biblioteca da IA não está instalada. Instale com: uv sync --extra ia"
            ) from erro
        try:
            cliente = anthropic.Anthropic(api_key=self._chave)
            with cliente.messages.stream(
                model=self.modelo,
                max_tokens=maximo_de_tokens,
                system=sistema,
                messages=[{"role": "user", "content": mensagem}],
            ) as fluxo:
                yield from fluxo.text_stream
        except (
            anthropic.APIConnectionError,
            anthropic.AuthenticationError,
            anthropic.RateLimitError,
            anthropic.APIStatusError,
        ) as erro:
            raise IaIndisponivel(_MENSAGEM_DE_FALHA) from erro

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        raise IaIndisponivel("Não há provedor de embeddings configurado; a busca usa só o BM25.")


_MENSAGEM_DE_FALHA = (
    "Não foi possível consultar a IA agora (sem internet, chave inválida ou limite "
    "de uso). O restante do aplicativo continua funcionando."
)


class ClienteOpenAICompativel:
    """Qualquer API no formato da OpenAI (`/chat/completions` e `/embeddings`).

    `base_url` inclui a versão quando o provedor exige (ex.: `https://api.openai.com/v1`,
    `http://localhost:11434/v1` no Ollama). Sem `chave` (Ollama local) não manda `Authorization`.
    """

    def __init__(
        self,
        base_url: str,
        chave: str | None,
        modelo: str,
        *,
        modelo_de_vetores: str | None = None,
        cliente_http: httpx.Client | None = None,
    ) -> None:
        self._base = validar_base_url(base_url)
        self._chave = chave
        self.modelo = modelo
        self.modelo_de_vetores = modelo_de_vetores
        self.capacidades = Capacidades(embeddings=modelo_de_vetores is not None, streaming=True)
        self._http = cliente_http or httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0))

    def __repr__(self) -> str:
        return f"ClienteOpenAICompativel(base_url={self._base!r}, modelo={self.modelo!r})"

    def _cabecalhos(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._chave}"} if self._chave else {}

    def _corpo(self, sistema: str, mensagem: str, maximo_de_tokens: int, fluxo: bool) -> dict:
        return {
            "model": self.modelo,
            "max_tokens": maximo_de_tokens,
            "temperature": 0,
            "stream": fluxo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": mensagem},
            ],
        }

    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        try:
            resposta = self._http.post(
                f"{self._base}/chat/completions",
                headers=self._cabecalhos(),
                json=self._corpo(sistema, mensagem, maximo_de_tokens, False),
            )
            resposta.raise_for_status()
            conteudo = resposta.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as erro:
            raise IaIndisponivel(_MENSAGEM_DE_FALHA) from erro
        return conteudo if isinstance(conteudo, str) else ""

    def completar_em_fluxo(
        self, sistema: str, mensagem: str, *, maximo_de_tokens: int
    ) -> Iterator[str]:
        try:
            with self._http.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers=self._cabecalhos(),
                json=self._corpo(sistema, mensagem, maximo_de_tokens, True),
            ) as resposta:
                resposta.raise_for_status()
                for linha in resposta.iter_lines():
                    if not linha.startswith("data:"):
                        continue
                    dado = linha.removeprefix("data:").strip()
                    if dado == "[DONE]":
                        return
                    delta = json.loads(dado)["choices"][0].get("delta", {}).get("content")
                    if delta:
                        yield delta
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as erro:
            raise IaIndisponivel(_MENSAGEM_DE_FALHA) from erro

    def vetorizar(self, textos: Sequence[str]) -> list[list[float]]:
        if self.modelo_de_vetores is None:
            raise IaIndisponivel("Não há modelo de embeddings configurado; a busca usa só o BM25.")
        try:
            resposta = self._http.post(
                f"{self._base}/embeddings",
                headers=self._cabecalhos(),
                json={"model": self.modelo_de_vetores, "input": list(textos)},
            )
            resposta.raise_for_status()
            itens = sorted(resposta.json()["data"], key=lambda item: item["index"])
            vetores = [[float(x) for x in item["embedding"]] for item in itens]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as erro:
            raise IaIndisponivel(_MENSAGEM_DE_FALHA) from erro
        if len(vetores) != len(textos):
            raise IaIndisponivel(_MENSAGEM_DE_FALHA)
        return vetores


def validar_base_url(base_url: str) -> str:
    """Só `http` e `https`, sem usuário e senha na URL (a chave vai em campo próprio, §12)."""
    partes = urlsplit(base_url.strip())
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        raise IaIndisponivel("O endereço do provedor deve começar com http:// ou https://.")
    if partes.username or partes.password:
        raise IaIndisponivel("Não coloque usuário nem senha no endereço; use o campo da chave.")
    return base_url.strip().rstrip("/")


class ClienteFalso:
    """Para os testes: respostas combinadas de antemão, e nenhuma chamada de rede."""

    def __init__(
        self,
        respostas: Sequence[str | Exception],
        vetores: Mapping[str, list[float]] | None = None,
        modelo_de_vetores: str | None = None,
    ) -> None:
        self._respostas = list(respostas)
        self._vetores = vetores
        self.modelo_de_vetores = modelo_de_vetores
        self.capacidades = Capacidades(embeddings=vetores is not None, streaming=True)
        self.chamadas: list[tuple[str, str]] = []

    def completar(self, sistema: str, mensagem: str, *, maximo_de_tokens: int) -> str:
        self.chamadas.append((sistema, mensagem))
        assert self._respostas, "ClienteFalso sem resposta combinada para esta chamada"
        resposta = self._respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def completar_em_fluxo(
        self, sistema: str, mensagem: str, *, maximo_de_tokens: int
    ) -> Iterator[str]:
        texto = self.completar(sistema, mensagem, maximo_de_tokens=maximo_de_tokens)
        for inicio in range(0, len(texto), 8):
            yield texto[inicio : inicio + 8]

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
