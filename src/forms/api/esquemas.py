"""Modelos Pydantic da API: entrada e saída em JSON (AGENTS.md §5.3).

Pydantic só existe nesta borda; o domínio usa `dataclasses`. Os nomes e campos destes modelos são
contrato com o `frontend/` (o TypeScript é gerado do OpenAPI): renomear ou remover campo de
resposta é mudança incompatível.

`definicao`, `valores` e `dados` são `object` de propósito: chegam como JSON não confiável e a
validação (com erros por `id` de campo) é do servidor, não do Pydantic.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from forms.dominio.exportacao import Coluna
from forms.dominio.models import (
    Campo,
    Definicao,
    ErroDeCampo,
    Formulario,
    Pasta,
    Registro,
    ResultadoCalculado,
    Versao,
)
from forms.repositorios.formularios import ResumoDeFormulario, ResumoDeVersao
from forms.servicos.servico import Catalogo


class Modelo(BaseModel):
    # Resposta com campo a mais ou a menos é bug de contrato: falha em vez de passar calada.
    model_config = ConfigDict(extra="forbid")


# --- erros ---


class PosicaoSaida(Modelo):
    """Trecho da fórmula (offsets em caracteres) para o front sublinhar."""

    inicio: int
    fim: int


class ErroDeCampoSaida(Modelo):
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


class ErroSaida(Modelo):
    """Formato uniforme de toda resposta de erro (401, 404, 409, 422...)."""

    detalhe: str
    erros: list[ErroDeCampoSaida] = Field(default_factory=list)
    codigo: str | None = Field(
        default=None,
        description="Código estável para o front agir (`token_expirado`, `termos_pendentes`...).",
    )


# --- formulários e versões ---


class FormularioEntrada(Modelo):
    nome: str
    definicao: object = Field(description='Definição em JSON: `{"campos": [...]}`.')
    pasta_id: int | None = Field(
        default=None, description="Pasta onde o formulário nasce; nulo (padrão) é a raiz."
    )


class DuplicarEntrada(Modelo):
    nome: str | None = Field(
        default=None,
        description='Nome da cópia. Sem ele, o padrão é "<nome> (cópia)", "(cópia 2)"…',
    )


class LoteEntrada(Modelo):
    formularios: list[FormularioEntrada]


class VersaoEntrada(Modelo):
    definicao: object


class ResumoDeFormularioSaida(Modelo):
    id: int
    nome: str
    criado_em: str
    versao_atual_id: int | None
    versao_atual_numero: int | None
    pasta_id: int | None = Field(default=None, description="Pasta do formulário; nulo é a raiz.")

    @classmethod
    def de(cls, resumo: ResumoDeFormulario) -> "ResumoDeFormularioSaida":
        return cls(
            id=resumo.id,
            nome=resumo.nome,
            criado_em=resumo.criado_em,
            versao_atual_id=resumo.versao_atual_id,
            versao_atual_numero=resumo.versao_atual_numero,
            pasta_id=resumo.pasta_id,
        )

    @classmethod
    def do_formulario(cls, formulario: Formulario, versao: Versao) -> "ResumoDeFormularioSaida":
        return cls(
            id=formulario.id,
            nome=formulario.nome,
            criado_em=formulario.criado_em,
            versao_atual_id=versao.id,
            versao_atual_numero=versao.numero,
            pasta_id=formulario.pasta_id,
        )


class CampoSaida(Modelo):
    """Um campo da definição. Só o que foi definido aparece (o resto é omitido, não é `null`)."""

    id: str
    tipo: Literal[
        "texto",
        "numero",
        "data",
        "selecao",
        "sim_nao",
        "calculado",
        "secao",
        "referencia",
        "localizacao",
    ]
    rotulo: str
    obrigatorio: bool | None = None
    unidade: str | None = None
    casas_decimais: int | None = None
    opcoes: list[str] | None = None
    formula: str | None = None
    formulario: str | None = None
    compartilhado: bool | None = None
    ia: bool | None = Field(
        default=None, description="`false`: o campo nunca é enviado à IA (§2.15)."
    )

    # Sem anotação de retorno de propósito: com `-> dict` o Pydantic trocaria o esquema do OpenAPI
    # por um objeto genérico, e o TypeScript gerado perderia os campos.
    @model_serializer(mode="wrap")
    def _omitir_o_que_nao_foi_definido(self, proximo: SerializerFunctionWrapHandler):
        # `unidade`, `opcoes`... ausentes não viram `null`: a definição sai como foi escrita.
        return {nome: valor for nome, valor in proximo(self).items() if valor is not None}

    @classmethod
    def de(cls, campo: Campo) -> "CampoSaida":
        return cls.model_validate(campo.para_json())


class ExibicaoSaida(Modelo):
    """Como o registro aparece em cartões e filtros; tudo opcional (§2.3)."""

    destaque: str | None = Field(default=None, description="Campo numérico em destaque.")
    status: str | None = Field(default=None, description="Campo calculado booleano de status.")
    resumo: list[str] = Field(default_factory=list, description="Campos do subtítulo.")


class DefinicaoSaida(Modelo):
    campos: list[CampoSaida]
    exibicao: ExibicaoSaida | None = None

    @classmethod
    def de(cls, definicao: Definicao) -> "DefinicaoSaida":
        exibicao = definicao.exibicao
        return cls(
            campos=[CampoSaida.de(campo) for campo in definicao.campos],
            exibicao=None
            if exibicao is None
            else ExibicaoSaida(
                destaque=exibicao.destaque, status=exibicao.status, resumo=list(exibicao.resumo)
            ),
        )

    # `exibicao` ausente não vira `null`: a definição sai como foi escrita.
    @model_serializer(mode="wrap")
    def _omitir_exibicao_vazia(self, proximo: SerializerFunctionWrapHandler):
        return {nome: valor for nome, valor in proximo(self).items() if valor is not None}


class VersaoSaida(Modelo):
    id: int
    formulario_id: int
    numero: int
    definicao: DefinicaoSaida
    publicada_em: str

    @classmethod
    def de(cls, versao: Versao) -> "VersaoSaida":
        return cls(
            id=versao.id,
            formulario_id=versao.formulario_id,
            numero=versao.numero,
            definicao=DefinicaoSaida.de(versao.definicao),
            publicada_em=versao.publicada_em,
        )


class ResumoDeVersaoSaida(Modelo):
    id: int
    numero: int
    publicada_em: str

    @classmethod
    def de(cls, resumo: ResumoDeVersao) -> "ResumoDeVersaoSaida":
        return cls(id=resumo.id, numero=resumo.numero, publicada_em=resumo.publicada_em)


class FormularioDetalheSaida(Modelo):
    id: int
    nome: str
    criado_em: str
    versao_atual: VersaoSaida
    pasta_id: int | None = Field(default=None, description="Pasta do formulário; nulo é a raiz.")


# --- pastas ---


class PastaEntrada(Modelo):
    nome: str
    pasta_pai_id: int | None = Field(
        default=None, description="Pasta onde a nova pasta nasce; nulo (padrão) é a raiz."
    )


class PastaAtualizacao(Modelo):
    """`PUT` substitui os dois campos (não há `PATCH`): omitir `pasta_pai_id` é erro, para não
    mandar a pasta para a raiz sem querer. Nulo explícito é a raiz."""

    nome: str
    pasta_pai_id: int | None


class MoverFormularioEntrada(Modelo):
    pasta_id: int | None = Field(description="Pasta de destino; nulo leva o formulário à raiz.")


class PastaSaida(Modelo):
    id: int
    nome: str
    pasta_pai_id: int | None
    criado_em: str

    @classmethod
    def de(cls, pasta: Pasta) -> "PastaSaida":
        return cls(
            id=pasta.id, nome=pasta.nome, pasta_pai_id=pasta.pasta_pai_id, criado_em=pasta.criado_em
        )


# --- definições: validar, prévia, catálogo ---


class ValidarEntrada(Modelo):
    definicao: object


class ValidarSaida(Modelo):
    """Responde 200 mesmo com erros: definição incompleta é o caso normal ao editar."""

    valida: bool
    erros: list[ErroDeCampoSaida]


class PreviaEntrada(Modelo):
    definicao: object
    valores: object = Field(
        default_factory=dict,
        description=(
            "Valores dos campos de entrada; em campo `referencia`, o id do registro de origem."
        ),
    )


class ResultadoCalculadoSaida(Modelo):
    valor: str | bool | None
    erro: str | None

    @classmethod
    def de(cls, resultado: ResultadoCalculado) -> "ResultadoCalculadoSaida":
        return cls(valor=resultado.valor, erro=resultado.erro)


class PreviaSaida(Modelo):
    valida: bool
    erros: list[ErroDeCampoSaida]
    calculados: dict[str, ResultadoCalculadoSaida]


class TipoDoCatalogoSaida(Modelo):
    id: str
    rotulo: str
    propriedades: list[str]


class FuncaoDoCatalogoSaida(Modelo):
    nome: str
    assinatura: str
    descricao: str
    exemplo: str


class ConstanteDoCatalogoSaida(Modelo):
    nome: str
    valor: str
    tipo: str
    descricao: str


class CatalogoSaida(Modelo):
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


class RegistroEntrada(Modelo):
    versao_id: int = Field(
        description="Versão que o front renderizou; o servidor não valida contra outra."
    )
    dados: object = Field(description="Só campos de entrada. Número como número ou string.")


class RegistroAtualizacao(Modelo):
    """`PUT` substitui todos os valores (não há `PATCH`)."""

    dados: object
    revisao: int = Field(
        description="A `revisao` do registro lida antes de editar; diferente → 409 (§2.14)."
    )


class PessoaResumoSaida(Modelo):
    id: int
    nome: str


class RegistroSaida(Modelo):
    id: int
    formulario_id: int
    versao_id: int
    dados: dict[str, object] = Field(
        description="Número sempre como string; campo calculado como `{valor, erro}`."
    )
    revisao: int = Field(description="Mande de volta no `PUT` (concorrência otimista).")
    criado_por: PessoaResumoSaida | None = Field(
        description="Nulo se a pessoa excluiu a conta (autoria anonimizada)."
    )
    atualizado_por: PessoaResumoSaida | None
    criado_em: str
    atualizado_em: str
    estado: Literal["conforme", "nao_conforme", "erro", "aguardando", "sem_status"] | None = Field(
        default=None,
        description="Estado do campo de status, decidido pelo servidor (§7). Só na listagem.",
    )

    @classmethod
    def de(
        cls,
        registro: Registro,
        nomes: Mapping[int, str] | None = None,
        estado: str | None = None,
    ) -> "RegistroSaida":
        nomes = nomes or {}

        def pessoa(id_: int | None) -> PessoaResumoSaida | None:
            if id_ is None or id_ not in nomes:
                return None
            return PessoaResumoSaida(id=id_, nome=nomes[id_])

        return cls(
            id=registro.id,
            formulario_id=registro.formulario_id,
            versao_id=registro.versao_id,
            dados=dict(registro.dados),
            revisao=registro.revisao,
            criado_por=pessoa(registro.criado_por),
            atualizado_por=pessoa(registro.atualizado_por),
            criado_em=registro.criado_em,
            atualizado_em=registro.atualizado_em,
            estado=estado,  # type: ignore[arg-type]  # o Pydantic confere o `Literal` na criação
        )


class ColunaSaida(Modelo):
    """Uma coluna da listagem, derivada da definição da versão listada (sem `secao`)."""

    id: str
    rotulo: str
    unidade: str | None
    tipo: Literal[
        "texto",
        "numero",
        "data",
        "selecao",
        "sim_nao",
        "calculado",
        "referencia",
        "localizacao",
    ]
    casas_decimais: int | None
    resultado: Literal["numero", "data", "booleano"] | None = Field(
        description="Para `calculado`: o tipo do resultado (diz como exibir o valor)."
    )
    opcoes: list[str] = Field(description="Para `selecao`: as opções; senão, lista vazia.")
    filtravel: bool = Field(
        description="Aceita `filtro=campo:valor` (igualdade) na listagem e no CSV."
    )


def coluna_de(coluna: Coluna) -> ColunaSaida:
    # `tipo` e `resultado` são `str` aqui e `Literal` no modelo: o Pydantic confere em execução.
    eh_calculado = coluna.tipo.value == "calculado" and coluna.tipo_na_formula is not None
    return ColunaSaida(
        id=coluna.id,
        rotulo=coluna.rotulo,
        unidade=coluna.unidade,
        tipo=coluna.tipo.value,
        casas_decimais=coluna.casas_decimais,
        resultado=coluna.tipo_na_formula.value if eh_calculado and coluna.tipo_na_formula else None,
        opcoes=list(coluna.opcoes),
        filtravel=coluna.filtravel,
    )


class ListagemDeRegistrosSaida(Modelo):
    versao_id: int = Field(description="Versão listada (a última, se `versao_id` não foi pedido).")
    colunas: list[ColunaSaida]
    itens: list[RegistroSaida]
    total: int
    exibicao: ExibicaoSaida = Field(
        description="Destaque, status e resumo efetivos (a definição, com o padrão onde faltar)."
    )


# --- pessoa, equipe, cargos, convites e termos (§2.12 a §2.15) ---


class PessoaSaida(Modelo):
    id: int
    nome: str
    email: str | None


class CargoResumoSaida(Modelo):
    id: int
    nome: str


class EquipeDaPessoaSaida(Modelo):
    id: int
    nome: str
    ativa: bool = Field(description="Falso quando a pessoa foi desativada nesta equipe.")
    cargo: CargoResumoSaida
    permissoes: list[str] = Field(description="Ids das permissões do cargo (para o front).")


class EuSaida(Modelo):
    """Quem sou eu: perfil, equipes com cargo e permissões, e os termos ainda por aceitar."""

    pessoa: PessoaSaida
    equipes: list[EquipeDaPessoaSaida]
    termos_pendentes: list[str]


class PermissaoSaida(Modelo):
    id: str
    grupo: str
    rotulo: str
    descricao: str


class CatalogoDePermissoesSaida(Modelo):
    permissoes: list[PermissaoSaida]


class CargoSaida(Modelo):
    id: int
    nome: str
    descricao: str
    padrao: bool
    permissoes: list[str]
    pessoas: int


class CargoEntrada(Modelo):
    nome: str = Field(min_length=1, max_length=80)
    descricao: str = Field(default="", max_length=300)
    permissoes: list[str] = Field(max_length=64)


class EquipeSaida(Modelo):
    id: int
    nome: str


class EquipeEntrada(Modelo):
    nome: str = Field(min_length=1, max_length=120)


class MembroSaida(Modelo):
    usuario_id: int
    nome: str
    email: str | None
    cargo: CargoResumoSaida
    ativo: bool
    entrou_em: str


class TrocarCargoEntrada(Modelo):
    cargo_id: int


class ConviteSaida(Modelo):
    id: int
    email: str
    cargo: CargoResumoSaida
    criado_em: str
    expira_em: str


class ConviteCriadoSaida(Modelo):
    convite: ConviteSaida
    token: str = Field(description="O token do convite. Só aparece nesta resposta.")


class ConviteEntrada(Modelo):
    email: str = Field(min_length=3, max_length=254)
    cargo_id: int


class AceitarConviteSaida(Modelo):
    equipe: EquipeSaida


class DocumentoLegalSaida(Modelo):
    id: str
    titulo: str
    versao: str
    markdown: str


class DocumentosLegaisSaida(Modelo):
    documentos: list[DocumentoLegalSaida]


class ConsentimentoSaida(Modelo):
    documento: str
    versao: str
    aceito_em: str


class ConsentimentosSaida(Modelo):
    aceites: list[ConsentimentoSaida]
    pendentes: list[str]


class ConsentimentoEntrada(Modelo):
    documentos: list[str] | None = Field(
        default=None, description="Documentos aceitos; omitido = todos os vigentes."
    )


class HistoricoSaida(Modelo):
    id: int
    usuario_id: int | None
    pessoa: str | None
    quando: str
    acao: str
    valores_anteriores: object | None
    motivo: str | None


class SaudeSaida(Modelo):
    status: Literal["ok"]


class ContagensSaida(Modelo):
    """Registros por estado do campo de status, com os mesmos filtros da listagem."""

    campo_status: str | None
    total: int
    conforme: int
    nao_conforme: int
    erro: int
    aguardando: int


class BuscaFormularioSaida(Modelo):
    id: int
    nome: str


class BuscaRegistroSaida(Modelo):
    id: int
    formulario_id: int
    formulario: str


class BuscaSaida(Modelo):
    formularios: list[BuscaFormularioSaida]
    registros: list[BuscaRegistroSaida]


class DestaqueSaida(Modelo):
    rotulo: str
    valor: str | None
    unidade: str | None


class RegistroRecenteSaida(Modelo):
    id: int
    formulario_id: int
    formulario: str
    atualizado_em: str
    estado: Literal["conforme", "nao_conforme", "erro", "aguardando", "sem_status"]
    destaque: DestaqueSaida | None


class NotificacaoSaida(Modelo):
    id: int
    tipo: Literal["convite_aceito", "cargo_alterado", "registro_editado", "erro_em_cascata"]
    referencia: dict[str, object]
    lida: bool
    criada_em: str


class NotificacoesSaida(Modelo):
    itens: list[NotificacaoSaida]
    nao_lidas: int


class ProgressoSaida(Modelo):
    tour_concluido: bool
    passo: int
    checklist_dispensado: bool


class ProgressoEntrada(Modelo):
    tour_concluido: bool
    passo: int = Field(ge=0, le=50)
    checklist_dispensado: bool


class ProntoSaida(Modelo):
    status: Literal["ok"]
    migracao: int = Field(description="Último número de migração aplicado.")


class ExemploSaida(Modelo):
    nome: str
    descricao: str
    campos: int
    depende_de: list[str] = Field(
        description="Nomes dos exemplos que este usa (importados juntos)."
    )


class ImportarExemplosEntrada(Modelo):
    nomes: list[str] = Field(min_length=1, max_length=20)


class ExemplosImportadosSaida(Modelo):
    formularios: list[str]


class RascunhoEntrada(Modelo):
    """O rascunho aceita definição incompleta (como o `validar`); só publicar valida (§2.2)."""

    definicao: object
    revisao: int | None = Field(
        default=None,
        description="Omitida ao criar o rascunho; a `revisao` lida ao substituí-lo (senão 409).",
    )


class RascunhoSaida(Modelo):
    formulario_id: int
    definicao: object
    base_versao_id: int | None = Field(description="A versão atual quando o rascunho nasceu.")
    revisao: int
    atualizado_por: PessoaResumoSaida | None
    atualizado_em: str


class GuiaSaida(Modelo):
    id: str
    titulo: str
    markdown: str = Field(description="Markdown para o front renderizar sem HTML cru.")


class GuiasSaida(Modelo):
    guias: list[GuiaSaida]
