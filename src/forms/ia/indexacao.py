"""Indexação dos registros e das definições como documentos de texto, por equipe (§2.5).

Cada registro vira **um texto determinístico**: `Formulário X · registro #N · criado em D por P ·
rótulo: valor ...`, com os valores já calculados pelo código. Fora dele, sempre: campo com
`"ia": false`, `localizacao` e `secao`. A sincronização é incremental e acontece quando o chat
precisa (compara o hash do texto), então o núcleo nunca importa este módulo.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from forms.dominio.models import Campo, TipoCampo, ValorJson, Versao
from forms.ia import repositorio as ia_repositorio
from forms.ia.cliente import IaIndisponivel, ProvedorDeLLM
from forms.infra.banco import Conexao
from forms.repositorios import extras as repositorio_extras
from forms.repositorios import formularios as repositorio

LOTE = 200
LOTE_DE_VETORES = 64


@dataclass(frozen=True)
class ResultadoDaSincronizacao:
    gravados: int
    removidos: int
    iguais: int


def campos_da_ia(versao: Versao) -> list[Campo]:
    """Os campos que a IA pode ver: nada de `ia: false`, localização nem seção (§2.15)."""
    return [
        c
        for c in versao.definicao.campos
        if c.ia and c.tipo not in (TipoCampo.LOCALIZACAO, TipoCampo.SECAO)
    ]


def _valor_em_texto(campo: Campo, guardado: ValorJson) -> str | None:
    valor = guardado
    if campo.tipo is TipoCampo.CALCULADO:
        if not isinstance(guardado, dict):
            return None
        if guardado.get("erro") is not None:
            return f"ERRO ({guardado['erro']})"
        valor = guardado.get("valor")
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if campo.tipo is TipoCampo.REFERENCIA:
        return f"registro #{valor}"
    texto = str(valor)
    if campo.casas_decimais is not None and isinstance(valor, str):
        try:
            texto = f"{Decimal(valor):.{campo.casas_decimais}f}"
        except ArithmeticError:
            pass
    return f"{texto} {campo.unidade}" if campo.unidade else texto


def texto_do_registro(
    formulario: str,
    registro_id: int,
    criado_em: str,
    autor: str | None,
    campos: list[Campo],
    dados: dict[str, ValorJson],
) -> str:
    partes = [f"Formulário {formulario}", f"registro #{registro_id}", f"criado em {criado_em[:10]}"]
    if autor:
        partes[-1] += f" por {autor}"
    for campo in campos:
        texto = _valor_em_texto(campo, dados.get(campo.id))
        if texto is not None:
            partes.append(f"{campo.rotulo}: {texto}")
    return " · ".join(partes)


def texto_da_definicao(formulario: str, versao: Versao) -> str:
    campos = campos_da_ia(versao)
    linhas = [f"Formulário {formulario} (versão {versao.numero}). Campos:"]
    for campo in campos:
        detalhe = campo.tipo.value + (f", {campo.unidade}" if campo.unidade else "")
        linha = f"- {campo.rotulo} ({detalhe})"
        if campo.formula:
            linha += f", calculado por: {campo.formula}"
        if campo.tipo is TipoCampo.REFERENCIA:
            linha += f", aponta para o formulário {campo.formulario}"
        linhas.append(linha)
    return "\n".join(linhas)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def sincronizar(conexao: Conexao, agora: datetime) -> ResultadoDaSincronizacao:
    """Põe os documentos da equipe em dia com os registros e as definições atuais."""
    existentes = ia_repositorio.documentos_existentes(conexao)
    vistos: set[tuple[str, int]] = set()
    gravados = iguais = 0
    versoes: dict[int, Versao] = {}

    def gravar(
        tipo: str, origem: int, formulario_id: int | None, texto: str, meta, criado_em: str | None
    ) -> None:
        nonlocal gravados, iguais
        vistos.add((tipo, origem))
        novo_hash = _hash(texto)
        antigo = existentes.get((tipo, origem))
        if antigo is not None and antigo[1] == novo_hash:
            iguais += 1
            return
        documento_id = ia_repositorio.gravar_documento(
            conexao, tipo, origem, formulario_id, texto, novo_hash, meta, criado_em, agora
        )
        if antigo is not None:  # o texto mudou: o vetor antigo já não vale
            ia_repositorio.apagar_vetores_do_documento(conexao, documento_id)
        gravados += 1

    for resumo in repositorio.listar_formularios(conexao):
        if resumo.versao_atual_id is None:
            continue
        versao = repositorio.obter_versao(conexao, resumo.versao_atual_id)
        gravar(
            "formulario",
            resumo.id,
            resumo.id,
            texto_da_definicao(resumo.nome, versao),
            {"formulario": resumo.nome, "tipo": "definicao"},
            None,
        )

    ultimo = 0
    while lote := ia_repositorio.registros_para_indexar(conexao, ultimo, LOTE):
        autores = repositorio_extras.nomes_de_usuarios(
            conexao, [r.criado_por for r in lote if r.criado_por is not None]
        )
        for r in lote:
            ultimo = r.id
            if r.versao_id not in versoes:
                versoes[r.versao_id] = repositorio.obter_versao(conexao, r.versao_id)
            autor = autores.get(r.criado_por or 0)
            texto = texto_do_registro(
                r.formulario, r.id, r.criado_em, autor, campos_da_ia(versoes[r.versao_id]), r.dados
            )
            gravar(
                "registro",
                r.id,
                r.formulario_id,
                texto,
                {"formulario": r.formulario, "registro_id": r.id, "data": r.criado_em[:10]},
                r.criado_em,
            )

    orfaos = {id_ for chave, (id_, _) in existentes.items() if chave not in vistos}
    ia_repositorio.apagar_documentos(conexao, orfaos)
    return ResultadoDaSincronizacao(gravados, len(orfaos), iguais)


def vetorizar_pendentes(conexao: Conexao, cliente: ProvedorDeLLM) -> int:
    """Calcula os embeddings que faltam (só se o provedor os tem). Devolve quantos gravou."""
    modelo = cliente.modelo_de_vetores
    if modelo is None:
        return 0
    total = 0
    while pendentes := ia_repositorio.documentos_sem_vetor(conexao, modelo, LOTE_DE_VETORES):
        try:
            vetores = cliente.vetorizar([texto for _, texto in pendentes])
        except IaIndisponivel:
            return total  # sem embeddings agora: a busca segue só com o BM25
        for (documento_id, _), vetor in zip(pendentes, vetores, strict=True):
            ia_repositorio.gravar_vetor(conexao, documento_id, modelo, vetor)
        total += len(pendentes)
    return total
