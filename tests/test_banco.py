"""Conexão, migrações e isolamento no banco (AGENTS.md §5.2, §12)."""

import psycopg
import pytest

from forms import banco
from forms.banco import Conexao, Migracao, SemContexto
from forms.models import Contexto


def test_migracoes_do_pacote_estao_numeradas_em_sequencia():
    # act
    numeros = [m.numero for m in banco.migracoes_do_pacote()]

    # assert
    assert numeros == list(range(1, len(numeros) + 1)) and numeros


def test_banco_migrado_registra_cada_migracao_uma_vez(conexao: Conexao):
    # act
    feitas = [
        linha[0] for linha in conexao.execute("SELECT numero FROM esquema_versao ORDER BY numero")
    ]

    # assert
    assert feitas == [m.numero for m in banco.migracoes_do_pacote()]


def test_migrar_de_novo_nao_aplica_nada(conexao: Conexao):
    # act / assert
    assert banco.migrar(conexao) == 0


def test_atualizacao_a_partir_do_esquema_anterior_aplica_so_as_novas(dsn: str):
    # arrange: um banco só com a 1ª migração e uma equipe já gravada nela
    base = psycopg.connect(dsn, autocommit=True)
    with base:
        base.execute("CREATE SCHEMA atualizacao")
        base.execute("SET search_path TO atualizacao")
        todas = banco.migracoes_do_pacote()
        primeira = [todas[0]]
        con = banco.abrir_conexao(dsn + "?options=-csearch_path%3Datualizacao%2Cpublic")
        try:
            banco.migrar(con, primeira)
            con.execute("INSERT INTO grupos (nome, criado_em) VALUES ('Antiga', now())")

            # act
            aplicadas = banco.migrar(con)

            # assert: as demais entram e os dados da equipe antiga continuam lá
            assert aplicadas == len(todas) - 1
            assert con.execute("SELECT nome FROM grupos").fetchone()["nome"] == "Antiga"
            assert con.execute("SELECT to_regclass('notificacoes')").fetchone()[0] is not None
        finally:
            con.close()
            base.execute("DROP SCHEMA atualizacao CASCADE")


def test_banco_de_versao_mais_nova_e_recusado(dsn: str):
    # arrange
    con = banco.abrir_conexao(dsn)
    con.execute("INSERT INTO esquema_versao (numero, nome) VALUES (9999, 'do_futuro.sql')")

    # act / assert
    try:
        with pytest.raises(banco.EsquemaMaisNovo, match="mais nova"):
            banco.migrar(con)
    finally:
        con.execute("DELETE FROM esquema_versao WHERE numero = 9999")
        con.close()


def test_migracao_que_falha_no_meio_nao_deixa_o_banco_pela_metade(dsn: str):
    # arrange
    con = banco.abrir_conexao(dsn)
    ruim = Migracao(500, "0500_ruim.sql", "CREATE TABLE so_a_metade (id int); SELECT 1/0;")

    # act
    with pytest.raises(psycopg.errors.DivisionByZero):
        banco.migrar(con, [*banco.migracoes_do_pacote(), ruim])

    # assert: nem a tabela, nem o registro da versão
    assert con.execute("SELECT to_regclass('so_a_metade')").fetchone()[0] is None
    assert con.execute("SELECT 1 FROM esquema_versao WHERE numero = 500").fetchone() is None
    con.close()


# --- contexto da conexão ---


def test_conexao_sem_contexto_recusa_a_equipe(dsn: str):
    # arrange
    con = banco.abrir_conexao(dsn)

    # act / assert
    with pytest.raises(SemContexto):
        con.grupo_id
    con.close()


def test_instantes_voltam_como_texto_iso_em_utc(conexao: Conexao):
    # act
    valor = conexao.execute("SELECT TIMESTAMPTZ '2026-11-02 07:00:00-03' AS t").fetchone()["t"]

    # assert
    assert valor == "2026-11-02T10:00:00+00:00"


# --- Row Level Security: a segunda barreira (a primeira é o `grupo_id` em cada consulta) ---


@pytest.fixture
def como_aplicativo(dsn: str):
    """Conexão no papel do app (`forms_app`, sem BYPASSRLS); o superusuário ignoraria o RLS."""
    con = banco.abrir_conexao(dsn)
    con.execute("SET ROLE forms_app")
    yield con
    con.execute("RESET ROLE")
    con.close()


def test_papel_do_aplicativo_nao_tem_bypass_de_rls(como_aplicativo: Conexao):
    # act
    linha = como_aplicativo.execute(
        "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
    ).fetchone()

    # assert
    assert linha["rolbypassrls"] is False and linha["rolsuper"] is False


def test_consulta_sem_filtro_de_equipe_so_enxerga_a_equipe_declarada(
    conexao: Conexao, outra_equipe: Conexao, dsn: str
):
    # arrange: cada equipe com um formulário
    conexao.execute(
        "INSERT INTO formularios (grupo_id, nome, nome_chave, criado_em)"
        " VALUES (%s, 'meu', 'meu', now())",
        (conexao.grupo_id,),
    )
    outra_equipe.execute(
        "INSERT INTO formularios (grupo_id, nome, nome_chave, criado_em)"
        " VALUES (%s, 'dela', 'dela', now())",
        (outra_equipe.grupo_id,),
    )
    app = banco.abrir_conexao(dsn)
    app.execute("SET ROLE forms_app")

    # act: SQL "esquecido", sem `WHERE grupo_id`
    sem_equipe = app.execute("SELECT nome FROM formularios").fetchall()
    app.definir_contexto(Contexto(conexao.grupo_id, None))
    da_minha = [linha["nome"] for linha in app.execute("SELECT nome FROM formularios")]

    # assert
    assert sem_equipe == [] and da_minha == ["meu"]
    app.execute("RESET ROLE")
    app.close()


def test_rls_barra_inserir_em_outra_equipe(conexao: Conexao, outra_equipe: Conexao, dsn: str):
    # arrange
    app = banco.abrir_conexao(dsn)
    app.execute("SET ROLE forms_app")
    app.definir_contexto(Contexto(conexao.grupo_id, None))

    # act / assert: declarar a equipe A e gravar na equipe B é recusado pelo banco
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app.execute(
            "INSERT INTO formularios (grupo_id, nome, nome_chave, criado_em)"
            " VALUES (%s, 'x', 'x', now())",
            (outra_equipe.grupo_id,),
        )
    app.execute("RESET ROLE")
    app.close()
