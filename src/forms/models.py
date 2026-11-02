"""Tipos comuns do domínio e exceções de domínio.

Módulo puro: sem I/O, sem Pydantic e sem importar nenhuma outra camada do projeto.
"""

from dataclasses import dataclass
from enum import StrEnum

# JSON arbitrário (valores de registro, por exemplo) sem recorrer a `Any`.
type ValorJson = None | bool | int | float | str | list[ValorJson] | dict[str, ValorJson]


class TipoCampo(StrEnum):
    TEXTO = "texto"
    NUMERO = "numero"
    DATA = "data"
    SELECAO = "selecao"
    SIM_NAO = "sim_nao"
    CALCULADO = "calculado"
    SECAO = "secao"
    REFERENCIA = "referencia"
    LOCALIZACAO = "localizacao"
    FOTO = "foto"


@dataclass(frozen=True)
class Campo:
    id: str
    tipo: TipoCampo
    rotulo: str
    obrigatorio: bool = False
    unidade: str | None = None
    casas_decimais: int | None = None
    # tupla (e não lista) para a imutabilidade valer de verdade
    opcoes: tuple[str, ...] = ()
    formula: str | None = None
    formulario: str | None = None
    compartilhado: bool = False
    maximo: int | None = None

    def para_json(self) -> dict[str, ValorJson]:
        """Forma canônica do contrato (§6): só o que não é padrão, na mesma ordem sempre."""
        dados: dict[str, ValorJson] = {
            "id": self.id,
            "tipo": self.tipo.value,
            "rotulo": self.rotulo,
        }
        if self.obrigatorio:
            dados["obrigatorio"] = True
        if self.unidade is not None:
            dados["unidade"] = self.unidade
        if self.casas_decimais is not None:
            dados["casas_decimais"] = self.casas_decimais
        if self.opcoes:
            dados["opcoes"] = list(self.opcoes)
        if self.formula is not None:
            dados["formula"] = self.formula
        if self.formulario is not None:
            dados["formulario"] = self.formulario
        if self.compartilhado:
            dados["compartilhado"] = True
        if self.maximo is not None:
            dados["maximo"] = self.maximo
        return dados

    @classmethod
    def de_json(cls, dados: dict[str, ValorJson]) -> "Campo":
        """Lê um campo que já foi validado (por exemplo, o guardado no banco); não valida."""
        return cls(
            id=str(dados["id"]),
            tipo=TipoCampo(str(dados["tipo"])),
            rotulo=str(dados["rotulo"]),
            obrigatorio=dados.get("obrigatorio") is True,
            unidade=_texto_ou_nulo(dados.get("unidade")),
            casas_decimais=_inteiro_ou_nulo(dados.get("casas_decimais")),
            opcoes=tuple(str(opcao) for opcao in _lista(dados.get("opcoes"))),
            formula=_texto_ou_nulo(dados.get("formula")),
            formulario=_texto_ou_nulo(dados.get("formulario")),
            compartilhado=dados.get("compartilhado") is True,
            maximo=_inteiro_ou_nulo(dados.get("maximo")),
        )


def _texto_ou_nulo(valor: ValorJson) -> str | None:
    return None if valor is None else str(valor)


def _inteiro_ou_nulo(valor: ValorJson) -> int | None:
    return None if valor is None else int(valor)


def _lista(valor: ValorJson) -> list[ValorJson]:
    return valor if isinstance(valor, list) else []


@dataclass(frozen=True)
class Definicao:
    campos: tuple[Campo, ...]

    def para_json(self) -> dict[str, ValorJson]:
        return {"campos": [campo.para_json() for campo in self.campos]}

    @classmethod
    def de_json(cls, dados: dict[str, ValorJson]) -> "Definicao":
        """Lê uma definição já validada (a guardada no banco); a entrada do usuário passa
        antes por `validacao.analisar_definicao`."""
        return cls(
            tuple(
                Campo.de_json(campo)
                for campo in _lista(dados.get("campos"))
                if isinstance(campo, dict)
            )
        )


@dataclass(frozen=True)
class Formulario:
    id: int
    nome: str
    criado_em: str


@dataclass(frozen=True)
class Versao:
    id: int
    formulario_id: int
    numero: int
    definicao: Definicao
    publicada_em: str


@dataclass(frozen=True)
class Registro:
    id: int
    formulario_id: int
    versao_id: int
    # O dict é mutável por dentro: os dados nascem de um JSON e copiá-los
    # profundamente a cada leitura custaria mais do que ajudaria.
    dados: dict[str, ValorJson]
    criado_em: str
    atualizado_em: str


@dataclass(frozen=True)
class Posicao:
    """Offsets do `ast` no texto da fórmula, para o front sublinhar o trecho (§5.3)."""

    inicio: int
    fim: int


@dataclass(frozen=True)
class ErroDeCampo:
    campo: str
    mensagem: str
    posicao: Posicao | None = None


@dataclass(frozen=True)
class ResultadoCalculado:
    """Formato `{"valor", "erro"}` de todo campo calculado (§7).

    Número e data viram string, então o valor guardado é texto, booleano ou vazio.
    """

    valor: str | bool | None
    erro: str | None


class ErroDeDominio(Exception):
    """Base de todas as exceções de domínio; `api.py` as traduz para HTTP."""


class FormulaInvalida(ErroDeDominio):
    def __init__(self, mensagem: str, posicao: Posicao | None = None) -> None:
        super().__init__(mensagem)
        self.posicao = posicao


class ErroDeCalculo(ErroDeDominio):
    """Falha ao executar uma fórmula válida (divisão por zero, por exemplo).

    Não é um erro de quem chama: `formulas.calcular_campos` o guarda no campo como `erro`.
    """


class DefinicaoInvalida(ErroDeDominio):
    def __init__(self, erros: tuple[ErroDeCampo, ...]) -> None:
        super().__init__("; ".join(f"{erro.campo}: {erro.mensagem}" for erro in erros))
        self.erros = erros


class CicloDeDependencia(DefinicaoInvalida):
    """Ciclo entre campos é uma definição inválida (422); cita os campos envolvidos."""

    def __init__(self, campos: tuple[str, ...]) -> None:
        mensagem = f"Dependência circular entre os campos: {' → '.join(campos)}"
        # O erro fica na fórmula do primeiro campo do ciclo, que o front consegue destacar.
        super().__init__((ErroDeCampo(campo=f"{campos[0]}.formula", mensagem=mensagem),))
        self.campos = campos


class RegistroInvalido(ErroDeDominio):
    def __init__(self, erros: tuple[ErroDeCampo, ...]) -> None:
        super().__init__("; ".join(f"{erro.campo}: {erro.mensagem}" for erro in erros))
        self.erros = erros


class ValorInvalido(ErroDeDominio):
    """Um valor isolado não serve para o tipo do campo; quem chama sabe de qual campo veio."""


class FotoInvalida(ErroDeDominio):
    """A imagem enviada não pode ser aceita; a mensagem já diz o motivo ao usuário."""


class NaoEncontrado(ErroDeDominio):
    pass


class ExclusaoBloqueada(ErroDeDominio):
    pass
