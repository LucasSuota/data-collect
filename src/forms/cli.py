"""Linha de comando de operação: migrar, criar equipe, importar template, registros (§2.4).

Só `argparse` e impressão: toda regra fica no `servico`. Erro de domínio vira mensagem em
português e código de saída 1; erro de uso do `argparse` sai com 2.

É para quem administra o servidor, não um atalho para furar permissões: os comandos de dados
exigem `--equipe` e `--usuario` explícitos e valem só o que o cargo daquela pessoa permite.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from forms import servico
from forms.exportacao import formatar_celula
from forms.models import (
    DefinicaoInvalida,
    ErroDeCampo,
    ErroDeDominio,
    LoteInvalido,
    RegistroInvalido,
    TipoCampo,
)

DSN_PADRAO = "postgresql://forms:forms@127.0.0.1:5433/forms"


def main(
    argv: Sequence[str] | None = None,
    relogio: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    args = _montar_parser().parse_args(argv)
    try:
        with closing(servico.abrir_banco(args.dsn, migrar=args.migrar_antes)) as conexao:
            if args.com_equipe:
                if args.equipe is None or args.usuario is None:
                    raise _UsoInvalido(
                        "Informe --equipe e --usuario (ou FORMS_EQUIPE e FORMS_USUARIO)."
                    )
                conexao.definir_contexto(
                    servico.contexto_da_pessoa(conexao, args.usuario, args.equipe)
                )
            return args.executar(conexao, args, relogio())
    except ErroDeDominio as erro:
        _imprimir_erro(erro)
    except OSError as erro:
        print(f"Erro: não foi possível ler ou gravar um arquivo: {erro}", file=sys.stderr)
    return 1


def _montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forms", description="Construtor de formulários modulares (linha de comando)."
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("FORMS_DATABASE_URL", DSN_PADRAO),
        help="endereço do PostgreSQL (padrão: variável FORMS_DATABASE_URL)",
    )
    parser.add_argument(
        "--equipe",
        type=int,
        default=_inteiro_do_ambiente("FORMS_EQUIPE"),
        help="id da equipe (padrão: variável FORMS_EQUIPE)",
    )
    parser.add_argument(
        "--usuario",
        type=int,
        default=_inteiro_do_ambiente("FORMS_USUARIO"),
        help="id da pessoa em nome de quem o comando roda (padrão: variável FORMS_USUARIO)",
    )
    comandos = parser.add_subparsers(dest="comando", required=True, metavar="comando")

    migrar = comandos.add_parser("migrar", help="aplica as migrações pendentes do banco")
    migrar.set_defaults(executar=_migrar, com_equipe=False, migrar_antes=False)

    equipe = comandos.add_parser(
        "criar-equipe", help="cria uma equipe e o convite do primeiro administrador"
    )
    equipe.add_argument("nome", help="nome da equipe")
    equipe.add_argument("--email", required=True, help="e-mail de quem será o administrador")
    equipe.set_defaults(executar=_criar_equipe, com_equipe=False, migrar_antes=False)

    importar = comandos.add_parser(
        "importar-template", help="cria formulários a partir de arquivos JSON"
    )
    importar.add_argument(
        "arquivos", nargs="+", type=Path, help="templates (o nome do arquivo é o do formulário)"
    )
    importar.add_argument("--nome", help="nome do formulário (só com um arquivo)")
    importar.set_defaults(executar=_importar_template, com_equipe=True, migrar_antes=False)

    criar = comandos.add_parser("criar-registro", help="cria um registro a partir de um JSON")
    criar.add_argument("formulario", help="nome ou id do formulário")
    criar.add_argument(
        "--dados", required=True, help="arquivo JSON com os valores (ou - para a entrada padrão)"
    )
    criar.add_argument("--versao", type=int, help="id da versão (padrão: a atual)")
    criar.set_defaults(executar=_criar_registro, com_equipe=True, migrar_antes=False)

    listar = comandos.add_parser(
        "listar", help="lista os formulários ou os registros de um formulário"
    )
    listar.add_argument("formulario", nargs="?", help="nome ou id; sem ele, lista os formulários")
    _argumentos_de_consulta(listar)
    listar.add_argument("--limite", type=int, default=servico.LIMITE_PADRAO)
    listar.add_argument("--deslocamento", type=int, default=0)
    listar.set_defaults(executar=_listar, com_equipe=True, migrar_antes=False)

    exportar = comandos.add_parser("exportar", help="exporta os registros em CSV para o Excel")
    exportar.add_argument("formulario", help="nome ou id do formulário")
    _argumentos_de_consulta(exportar)
    exportar.add_argument("--saida", type=Path, help="arquivo CSV (padrão: saída padrão)")
    exportar.set_defaults(executar=_exportar, com_equipe=True, migrar_antes=False)
    return parser


def _argumentos_de_consulta(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--versao", type=int, help="id da versão (padrão: a última)")
    parser.add_argument(
        "--filtro",
        action="append",
        default=[],
        metavar="CAMPO=VALOR",
        help="igualdade; pode repetir",
    )


# --- comandos ---


def _migrar(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    aplicadas = servico.migrar_banco(conexao)
    print(f"{aplicadas} migração(ões) aplicada(s).")
    return 0


def _criar_equipe(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    token = servico.garantir_primeiro_administrador(conexao, args.email, args.nome, agora)
    if token is None:
        print("Já existe uma equipe: use o convite dentro do app.", file=sys.stderr)
        return 1
    print(f"Equipe '{args.nome}' criada. Abra no app: /convite/{token}")
    return 0


def _importar_template(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    if args.nome and len(args.arquivos) != 1:
        raise _UsoInvalido("--nome só vale quando se importa um único arquivo.")
    if len(args.arquivos) == 1:
        criados = [servico.importar_template(conexao, args.arquivos[0], agora, args.nome)]
    else:
        criados = servico.importar_templates(conexao, args.arquivos, agora)
    for criado in criados:
        print(
            f"Formulário '{criado.formulario.nome}' criado "
            f"(id {criado.formulario.id}, versão {criado.versao.numero})."
        )
    return 0


def _criar_registro(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    formulario = servico.localizar_formulario(conexao, args.formulario)
    versao_id = args.versao or formulario.versao_atual.id
    registro = servico.criar_registro(
        conexao, formulario.formulario.id, versao_id, _ler_dados(args.dados), agora
    )
    print(f"Registro {registro.id} criado no formulário '{formulario.formulario.nome}'.")
    # O registro novo é o primeiro da listagem (do mais recente ao mais antigo).
    listagem = servico.listar_registros(
        conexao, formulario.formulario.id, versao_id=versao_id, limite=1
    )
    for coluna in listagem.colunas:
        if coluna.tipo is TipoCampo.CALCULADO:
            print(f"  {coluna.cabecalho}: {formatar_celula(coluna, registro.dados.get(coluna.id))}")
    return 0


def _listar(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    if args.formulario is None:
        for resumo in servico.listar_formularios(conexao):
            print(f"{resumo.id}\t{resumo.nome}\tversão {resumo.versao_atual_numero}")
        return 0

    formulario = servico.localizar_formulario(conexao, args.formulario)
    listagem = servico.listar_registros(
        conexao,
        formulario.formulario.id,
        versao_id=args.versao,
        filtros=_ler_filtros(args.filtro),
        limite=args.limite,
        deslocamento=args.deslocamento,
    )
    print("\t".join(["id", *(coluna.cabecalho for coluna in listagem.colunas)]))
    for registro in listagem.itens:
        celulas = (formatar_celula(c, registro.dados.get(c.id)) for c in listagem.colunas)
        print("\t".join([str(registro.id), *celulas]))
    print(f"{listagem.total} registro(s)")
    return 0


def _exportar(conexao: servico.Conexao, args: argparse.Namespace, agora: datetime) -> int:
    formulario = servico.localizar_formulario(conexao, args.formulario)
    conteudo = servico.exportar_csv(
        conexao, formulario.formulario.id, versao_id=args.versao, filtros=_ler_filtros(args.filtro)
    )
    if args.saida is None:
        # Bytes, para o BOM chegar inteiro a um redirecionamento (`> arquivo.csv`).
        sys.stdout.buffer.write(conteudo)
        sys.stdout.buffer.flush()
    else:
        args.saida.write_bytes(conteudo)
        print(f"CSV gravado em {args.saida}.")
    return 0


# --- entrada e saída ---


class _UsoInvalido(ErroDeDominio):
    """Combinação de argumentos que o `argparse` não consegue recusar sozinho."""


def _inteiro_do_ambiente(nome: str) -> int | None:
    valor = os.environ.get(nome, "").strip()
    return int(valor) if valor.isdigit() else None


def _ler_dados(origem: str) -> object:
    texto = sys.stdin.read() if origem == "-" else Path(origem).read_text(encoding="utf-8")
    try:
        return json.loads(texto)
    except json.JSONDecodeError as erro:
        raise _UsoInvalido(f"Os dados não são um JSON válido: {erro}.") from erro


def _ler_filtros(filtros: Sequence[str]) -> dict[str, str]:
    lidos = {}
    for filtro in filtros:
        campo, separador, valor = filtro.partition("=")
        if not separador or not campo:
            raise _UsoInvalido(f"O filtro '{filtro}' deve ter o formato campo=valor.")
        lidos[campo] = valor
    return lidos


def _imprimir_erro(erro: ErroDeDominio) -> None:
    if isinstance(erro, LoteInvalido):
        for formulario in erro.formularios:
            print(f"Erro no formulário '{formulario.nome}':", file=sys.stderr)
            _imprimir_campos(formulario.erros)
    elif isinstance(erro, DefinicaoInvalida | RegistroInvalido):
        print("Erro:", file=sys.stderr)
        _imprimir_campos(erro.erros)
    else:
        print(f"Erro: {erro}", file=sys.stderr)


def _imprimir_campos(erros: Sequence[ErroDeCampo]) -> None:
    for erro in erros:
        print(f"  {erro.campo}: {erro.mensagem}", file=sys.stderr)
