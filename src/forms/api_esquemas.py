"""Modelos Pydantic da API: entrada e saída em JSON (AGENTS.md §5.3).

Pydantic só existe nesta borda; o domínio usa `dataclasses`. Os nomes e campos destes modelos são
contrato com o `frontend/` (o TypeScript é gerado do OpenAPI): renomear ou remover campo de
resposta é mudança incompatível.

`definicao`, `valores` e `dados` são `object` de propósito: chegam como JSON não confiável e a
validação (com erros por `id` de campo) é do servidor, não do Pydantic.
"""

from pydantic import BaseModel, ConfigDict, Field

from forms.models import ErroDeCampo, Formulario, Registro, ResultadoCalculado, Versao
from forms.repositorio import ResumoDeFormulario, ResumoDeVersao
from forms.servico import Catalogo


class _Modelo(BaseModel):
    # Resposta com campo a mais ou a menos é bug de contrato: falha em vez de passar calada.
    model_config = ConfigDict(extra="forbid")


# --- erros ---


class PosicaoSaida(_Modelo):
    """Trecho da fórmula (offsets em caracteres) para o front sublinhar."""

    inicio: int
    fim: int


class ErroDeCampoSaida(_Modelo):
    campo: str = Field(description="`id` do campo, ex.: `resistencia_mpa.formula`.")
    mensagem: str
    posicao: PosicaoSaida | None = None

    @classmethod
    def de(cls, erro: ErroDeCampo, prefixo: str = "") -> "ErroDeCampoSaida":
        posicao = erro.posicao
        return cls(
            campo=f"{prefixo}{erro.campo}",
            mensagem=erro.mensagem,
            posicao=None
            if posicao is None
            else PosicaoSaida(inicio=posicao.inicio, fim=posicao.fim),
        )


class ErroSaida(_Modelo):
    """Formato uniforme de toda resposta de erro (401, 404, 409, 422...)."""

    detalhe: str
    erros: list[ErroDeCampoSaida] = Field(default_factory=list)


# --- formulários e versões ---


class FormularioEntrada(_Modelo):
    nome: str
    definicao: object = Field(description='Definição em JSON: `{"campos": [...]}`.')


class LoteEntrada(_Modelo):
    formularios: list[FormularioEntrada]


class VersaoEntrada(_Modelo):
    definicao: object


class ResumoDeFormularioSaida(_Modelo):
    id: int
    nome: str
    criado_em: str
    versao_atual_id: int | None
    versao_atual_numero: int | None

    @classmethod
    def de(cls, resumo: ResumoDeFormulario) -> "ResumoDeFormularioSaida":
        return cls(
            id=resumo.id,
            nome=resumo.nome,
            criado_em=resumo.criado_em,
            versao_atual_id=resumo.versao_atual_id,
            versao_atual_numero=resumo.versao_atual_numero,
        )

    @classmethod
    def do_formulario(cls, formulario: Formulario, versao: Versao) -> "ResumoDeFormularioSaida":
        return cls(
            id=formulario.id,
            nome=formulario.nome,
            criado_em=formulario.criado_em,
            versao_atual_id=versao.id,
            versao_atual_numero=versao.numero,
        )


class VersaoSaida(_Modelo):
    id: int
    formulario_id: int
    numero: int
    definicao: dict[str, object]
    publicada_em: str

    @classmethod
    def de(cls, versao: Versao) -> "VersaoSaida":
        return cls(
            id=versao.id,
            formulario_id=versao.formulario_id,
            numero=versao.numero,
            definicao=versao.definicao.para_json(),
            publicada_em=versao.publicada_em,
        )


class ResumoDeVersaoSaida(_Modelo):
    id: int
    numero: int
    publicada_em: str

    @classmethod
    def de(cls, resumo: ResumoDeVersao) -> "ResumoDeVersaoSaida":
        return cls(id=resumo.id, numero=resumo.numero, publicada_em=resumo.publicada_em)


class FormularioDetalheSaida(_Modelo):
    id: int
    nome: str
    criado_em: str
    versao_atual: VersaoSaida


# --- definições: validar, prévia, catálogo ---


class ValidarEntrada(_Modelo):
    definicao: object


class ValidarSaida(_Modelo):
    """Responde 200 mesmo com erros: definição incompleta é o caso normal ao editar."""

    valida: bool
    erros: list[ErroDeCampoSaida]


class PreviaEntrada(_Modelo):
    definicao: object
    valores: object = Field(
        default_factory=dict,
        description=(
            "Valores dos campos de entrada; em campo `referencia`, o id do registro de origem."
        ),
    )


class ResultadoCalculadoSaida(_Modelo):
    valor: str | bool | None
    erro: str | None

    @classmethod
    def de(cls, resultado: ResultadoCalculado) -> "ResultadoCalculadoSaida":
        return cls(valor=resultado.valor, erro=resultado.erro)


class PreviaSaida(_Modelo):
    valida: bool
    erros: list[ErroDeCampoSaida]
    calculados: dict[str, ResultadoCalculadoSaida]


class TipoDoCatalogoSaida(_Modelo):
    id: str
    rotulo: str
    propriedades: list[str]


class FuncaoDoCatalogoSaida(_Modelo):
    nome: str
    assinatura: str
    descricao: str
    exemplo: str


class ConstanteDoCatalogoSaida(_Modelo):
    nome: str
    valor: str
    tipo: str
    descricao: str


class CatalogoSaida(_Modelo):
    tipos: list[TipoDoCatalogoSaida]
    funcoes: list[FuncaoDoCatalogoSaida]
    constantes: list[ConstanteDoCatalogoSaida]
    nomes_reservados: list[str]

    @classmethod
    def de(cls, catalogo: Catalogo) -> "CatalogoSaida":
        return cls(
            tipos=[
                TipoDoCatalogoSaida(id=t.id, rotulo=t.rotulo, propriedades=list(t.propriedades))
                for t in catalogo.tipos
            ],
            funcoes=[
                FuncaoDoCatalogoSaida(
                    nome=f.nome, assinatura=f.assinatura, descricao=f.descricao, exemplo=f.exemplo
                )
                for f in catalogo.funcoes
            ],
            constantes=[
                ConstanteDoCatalogoSaida(
                    nome=c.nome, valor=c.valor, tipo=c.tipo, descricao=c.descricao
                )
                for c in catalogo.constantes
            ],
            nomes_reservados=list(catalogo.nomes_reservados),
        )


# --- registros ---


class RegistroEntrada(_Modelo):
    versao_id: int = Field(
        description="Versão que o front renderizou; o servidor não valida contra outra."
    )
    dados: object = Field(description="Só campos de entrada. Número como número ou string.")


class RegistroAtualizacao(_Modelo):
    """`PUT` substitui todos os valores (não há `PATCH`)."""

    dados: object


class RegistroSaida(_Modelo):
    id: int
    formulario_id: int
    versao_id: int
    dados: dict[str, object] = Field(
        description="Número sempre como string; campo calculado como `{valor, erro}`."
    )
    criado_em: str
    atualizado_em: str

    @classmethod
    def de(cls, registro: Registro) -> "RegistroSaida":
        return cls(
            id=registro.id,
            formulario_id=registro.formulario_id,
            versao_id=registro.versao_id,
            dados=dict(registro.dados),
            criado_em=registro.criado_em,
            atualizado_em=registro.atualizado_em,
        )


class ListagemDeRegistrosSaida(_Modelo):
    versao_id: int = Field(description="Versão listada (a última, se `versao_id` não foi pedido).")
    itens: list[RegistroSaida]
    total: int


# --- anexos ---


class AnexoSaida(_Modelo):
    id: int
    largura: int
    altura: int
    tamanho_bytes: int
