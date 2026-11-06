"""Equipes, cargos, convites e termos no serviço (AGENTS.md §2.12 a §2.15)."""

from datetime import UTC, datetime, timedelta

import pytest

from forms.dominio.models import (
    CargoInvalido,
    Contexto,
    NaoEncontrado,
    SemAcessoAEquipe,
    SemPermissao,
    ValorInvalido,
)
from forms.dominio.permissoes import CARGOS_PADRAO, IDS_DE_PERMISSAO
from forms.infra import banco, segredos
from forms.infra.banco import Conexao
from forms.repositorios import equipes as repositorio_equipes
from forms.servicos import equipes as servico_equipes

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def sem_contexto(dsn: str) -> Conexao:
    from forms.infra import banco

    con = banco.abrir_conexao(dsn)
    yield con
    con.close()


def _equipe_com_admin(con: Conexao, nome: str = "Obra") -> tuple[int, int, int]:
    """(grupo, administrador, id do cargo Administrador) com a conexão já na equipe."""
    grupo, admin_cargo = servico_equipes.criar_equipe(con, nome, AGORA)
    admin = servico_equipes.identificar(con, f"sub-{nome}", "Admin", "a@x.example", AGORA)
    repositorio_equipes.adicionar_membro(con, grupo.id, admin.id, admin_cargo.id, AGORA)
    con.definir_contexto(servico_equipes.contexto_da_pessoa(con, admin.id, grupo.id))
    return grupo.id, admin.id, admin_cargo.id


def _cargo(con: Conexao, nome: str) -> int:
    return next(c.id for c in servico_equipes.listar_cargos(con) if c.nome == nome)


def _pessoa(con: Conexao, sub: str, grupo: int, cargo: str) -> int:
    usuario = servico_equipes.identificar(con, sub, sub.title(), f"{sub}@x.example", AGORA)
    repositorio_equipes.adicionar_membro(con, grupo, usuario.id, _cargo(con, cargo), AGORA)
    return usuario.id


# --- criar equipe ---


def test_criar_equipe_semeia_os_cinco_cargos_de_partida_com_as_permissoes_do_design(
    sem_contexto: Conexao,
):
    # act
    grupo, administrador = servico_equipes.criar_equipe(sem_contexto, "Obra", AGORA)
    sem_contexto.definir_contexto(Contexto(grupo.id, None))
    cargos = {c.nome: c for c in servico_equipes.listar_cargos(sem_contexto)}

    # assert
    assert set(cargos) == {c.nome for c in CARGOS_PADRAO}
    assert set(administrador.permissoes) == IDS_DE_PERMISSAO and len(IDS_DE_PERMISSAO) == 17
    assert len(cargos["Engenheiro"].permissoes) == 11
    assert "registros:excluir" not in cargos["Engenheiro"].permissoes
    assert set(cargos["Visualizador"].permissoes) == {"formularios:ver", "registros:ver"}
    assert all(c.padrao for c in cargos.values())


def test_criar_equipe_sem_nome_e_erro(sem_contexto: Conexao):
    # act / assert
    with pytest.raises(ValorInvalido):
        servico_equipes.criar_equipe(sem_contexto, "   ", AGORA)


def test_cargos_de_uma_equipe_nao_aparecem_em_outra(sem_contexto: Conexao):
    # arrange
    a, _, _ = _equipe_com_admin(sem_contexto, "A")
    cargo_da_a = _cargo(sem_contexto, "Gestor")
    b, _, _ = _equipe_com_admin(sem_contexto, "B")

    # act / assert
    assert cargo_da_a not in {c.id for c in servico_equipes.listar_cargos(sem_contexto)}
    assert a != b


# --- identificar e contexto ---


def test_primeiro_acesso_cria_a_pessoa_e_busca_o_perfil_no_logto(sem_contexto: Conexao):
    # act
    usuario = servico_equipes.identificar(
        sem_contexto, "sub-nova", None, None, AGORA, perfil=lambda sub: ("Nova Pessoa", "n@x.io")
    )

    # assert
    assert (usuario.nome, usuario.email) == ("Nova Pessoa", "n@x.io")


def test_logto_fora_do_ar_nao_impede_o_primeiro_acesso(sem_contexto: Conexao):
    # arrange
    def quebrado(sub: str):
        raise NaoEncontrado("fora do ar")

    # act
    usuario = servico_equipes.identificar(sem_contexto, "sub-x", None, None, AGORA, quebrado)

    # assert
    assert usuario.nome == "Pessoa sem nome"


def test_acessos_seguidos_nao_regravam_o_ultimo_acesso_a_cada_requisicao(sem_contexto: Conexao):
    # arrange
    primeiro = servico_equipes.identificar(sem_contexto, "sub-y", "Y", None, AGORA)

    # act
    logo_depois = servico_equipes.identificar(
        sem_contexto, "sub-y", "Y", None, AGORA + timedelta(minutes=1)
    )
    bem_depois = servico_equipes.identificar(
        sem_contexto, "sub-y", "Y", None, AGORA + timedelta(minutes=10)
    )

    # assert
    assert logo_depois.ultimo_acesso_em == primeiro.ultimo_acesso_em
    assert bem_depois.ultimo_acesso_em == "2026-11-02T10:10:00+00:00"


def test_contexto_traz_as_permissoes_do_cargo_lidas_do_banco(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    tecnico = _pessoa(sem_contexto, "tec", grupo, "Técnico")

    # act
    contexto = servico_equipes.contexto_da_pessoa(sem_contexto, tecnico, grupo)

    # assert
    assert contexto.tem("registros:criar") and not contexto.tem("registros:excluir")


def test_quem_nao_e_membro_ou_foi_desativado_nao_tem_contexto(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    colega = _pessoa(sem_contexto, "colega", grupo, "Visualizador")
    intrusa = servico_equipes.identificar(sem_contexto, "sub-intrusa", "I", None, AGORA).id

    # act / assert
    with pytest.raises(SemAcessoAEquipe):
        servico_equipes.contexto_da_pessoa(sem_contexto, intrusa, grupo)
    servico_equipes.desativar_pessoa(sem_contexto, colega)
    with pytest.raises(SemAcessoAEquipe):
        servico_equipes.contexto_da_pessoa(sem_contexto, colega, grupo)


# --- cargos: regras ---


def test_cargo_novo_com_permissoes_validas(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)

    # act
    cargo = servico_equipes.criar_cargo(
        sem_contexto, "Supervisor", "Confere os ensaios", ["registros:ver", "historico:ver"]
    )

    # assert
    assert cargo.nome == "Supervisor" and not cargo.padrao
    assert set(cargo.permissoes) == {"registros:ver", "historico:ver"}


@pytest.mark.parametrize(
    ("nome", "permissoes", "campo"),
    [
        ("", ["registros:ver"], "nome"),
        ("Administrador", ["registros:ver"], "nome"),  # repetido
        ("  administrador ", ["registros:ver"], "nome"),  # repetido, outra caixa e espaços
        ("Novo", ["registros:voar"], "permissoes"),  # inexistente
    ],
)
def test_cargo_invalido_e_recusado_com_o_erro_no_campo(
    sem_contexto: Conexao, nome: str, permissoes: list[str], campo: str
):
    # arrange
    _equipe_com_admin(sem_contexto)

    # act / assert
    with pytest.raises(CargoInvalido) as erro:
        servico_equipes.criar_cargo(sem_contexto, nome, "", permissoes)
    assert campo in {e.campo for e in erro.value.erros}


def test_ninguem_concede_permissao_que_nao_tem(sem_contexto: Conexao):
    # arrange: uma pessoa com poder de editar cargos, mas sem excluir registros
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    limitado = servico_equipes.criar_cargo(
        sem_contexto, "Chefe", "", ["cargos:editar", "registros:ver"]
    )
    chefe = servico_equipes.identificar(sem_contexto, "sub-chefe", "Chefe", None, AGORA)
    repositorio_equipes.adicionar_membro(sem_contexto, grupo, chefe.id, limitado.id, AGORA)
    sem_contexto.definir_contexto(servico_equipes.contexto_da_pessoa(sem_contexto, chefe.id, grupo))

    # act / assert: escalar privilégio por um cargo novo é recusado
    with pytest.raises(CargoInvalido, match="registros:excluir"):
        servico_equipes.criar_cargo(sem_contexto, "Super", "", ["registros:excluir"])


def test_cargo_em_uso_nao_pode_ser_excluido_mas_sem_pessoas_pode(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    em_uso = servico_equipes.criar_cargo(sem_contexto, "Em uso", "", ["registros:ver"])
    livre = servico_equipes.criar_cargo(sem_contexto, "Livre", "", ["registros:ver"])
    pessoa = servico_equipes.identificar(sem_contexto, "sub-p", "P", None, AGORA)
    repositorio_equipes.adicionar_membro(sem_contexto, grupo, pessoa.id, em_uso.id, AGORA)

    # act
    servico_equipes.excluir_cargo(sem_contexto, livre.id)

    # assert
    with pytest.raises(CargoInvalido, match="pessoas"):
        servico_equipes.excluir_cargo(sem_contexto, em_uso.id)
    assert "Livre" not in {c.nome for c in servico_equipes.listar_cargos(sem_contexto)}


def test_editar_cargo_muda_as_permissoes_de_quem_o_tem_na_hora(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    tecnico = _pessoa(sem_contexto, "tec", grupo, "Técnico")
    cargo_id = _cargo(sem_contexto, "Técnico")
    antes = servico_equipes.contexto_da_pessoa(sem_contexto, tecnico, grupo)

    # act
    servico_equipes.atualizar_cargo(
        sem_contexto, cargo_id, "Técnico", "", ["formularios:ver", "registros:ver"]
    )
    depois = servico_equipes.contexto_da_pessoa(sem_contexto, tecnico, grupo)

    # assert
    assert antes.tem("registros:criar") and not depois.tem("registros:criar")


# --- sempre existe um administrador ---


def test_o_unico_administrador_nao_pode_ser_rebaixado_desativado_nem_sair(sem_contexto: Conexao):
    # arrange
    grupo, admin, _ = _equipe_com_admin(sem_contexto)
    visualizador = _cargo(sem_contexto, "Visualizador")

    # act / assert
    with pytest.raises(CargoInvalido, match="administrador"):
        servico_equipes.mudar_cargo(sem_contexto, admin, visualizador)
    with pytest.raises(CargoInvalido, match="administrador"):
        servico_equipes.desativar_pessoa(sem_contexto, admin)
    with pytest.raises(CargoInvalido, match="administrador"):
        servico_equipes.sair_da_equipe(sem_contexto)
    assert servico_equipes.contexto_da_pessoa(sem_contexto, admin, grupo).tem("cargos:editar")


def test_com_dois_administradores_um_pode_ser_rebaixado(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    segundo = _pessoa(sem_contexto, "segundo", grupo, "Administrador")

    # act
    servico_equipes.mudar_cargo(sem_contexto, segundo, _cargo(sem_contexto, "Gestor"))

    # assert
    assert not servico_equipes.contexto_da_pessoa(sem_contexto, segundo, grupo).tem("cargos:editar")


def test_tirar_a_permissao_de_administrar_do_unico_cargo_que_a_tem_e_recusado(
    sem_contexto: Conexao,
):
    # arrange
    _, _, admin_cargo = _equipe_com_admin(sem_contexto)

    # act / assert
    with pytest.raises(CargoInvalido, match="ao menos uma pessoa"):
        servico_equipes.atualizar_cargo(
            sem_contexto, admin_cargo, "Administrador", "", ["registros:ver"]
        )


def test_so_se_atribui_cargo_que_a_pessoa_pode_conceder(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    gerente = servico_equipes.criar_cargo(
        sem_contexto, "Gerente", "", ["equipe:atribuir_cargos", "equipe:convidar", "registros:ver"]
    )
    ana = servico_equipes.identificar(sem_contexto, "sub-ana", "Ana", None, AGORA)
    repositorio_equipes.adicionar_membro(sem_contexto, grupo, ana.id, gerente.id, AGORA)
    visualizador = _pessoa(sem_contexto, "vis", grupo, "Visualizador")
    admin_cargo = _cargo(sem_contexto, "Administrador")
    sem_contexto.definir_contexto(servico_equipes.contexto_da_pessoa(sem_contexto, ana.id, grupo))

    # act / assert: promover alguém a administrador sem ser administrador é recusado
    with pytest.raises(SemPermissao):
        servico_equipes.mudar_cargo(sem_contexto, visualizador, admin_cargo)
    with pytest.raises(SemPermissao):
        servico_equipes.criar_convite(sem_contexto, "x@y.io", admin_cargo, AGORA)


# --- convites ---


def test_convite_guarda_so_o_hash_do_token(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)

    # act
    convite_id, token = servico_equipes.criar_convite(
        sem_contexto, "nova@x.io", _cargo(sem_contexto, "Técnico"), AGORA
    )

    # assert
    guardado = sem_contexto.execute(
        "SELECT token_hash FROM convites WHERE id = %s", (convite_id,)
    ).fetchone()["token_hash"]
    assert guardado == segredos.hash_do_token(token) and token not in guardado
    dump = [dict(linha) for linha in sem_contexto.execute("SELECT * FROM convites")]
    assert token not in str(dump)


def test_aceitar_convite_coloca_a_pessoa_na_equipe_com_o_cargo_do_convite(sem_contexto: Conexao):
    # arrange
    grupo, _, _ = _equipe_com_admin(sem_contexto)
    _, token = servico_equipes.criar_convite(
        sem_contexto, "nova@x.io", _cargo(sem_contexto, "Técnico"), AGORA
    )
    nova = servico_equipes.identificar(sem_contexto, "sub-nova", "Nova", None, AGORA)

    # act
    equipe = servico_equipes.aceitar_convite(sem_contexto, token, nova.id, AGORA)

    # assert
    assert equipe.id == grupo
    contexto = servico_equipes.contexto_da_pessoa(sem_contexto, nova.id, grupo)
    assert contexto.tem("registros:criar") and not contexto.tem("cargos:editar")


def test_convite_so_vale_uma_vez(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)
    _, token = servico_equipes.criar_convite(
        sem_contexto, "a@x.io", _cargo(sem_contexto, "Técnico"), AGORA
    )
    primeira = servico_equipes.identificar(sem_contexto, "sub-1", "Um", None, AGORA)
    segunda = servico_equipes.identificar(sem_contexto, "sub-2", "Dois", None, AGORA)
    servico_equipes.aceitar_convite(sem_contexto, token, primeira.id, AGORA)

    # act / assert
    with pytest.raises(ValorInvalido, match="já foi usado"):
        servico_equipes.aceitar_convite(sem_contexto, token, segunda.id, AGORA)


def test_convite_expirado_revogado_ou_inexistente_e_recusado(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)
    cargo = _cargo(sem_contexto, "Técnico")
    _, velho = servico_equipes.criar_convite(sem_contexto, "a@x.io", cargo, AGORA)
    revogado_id, revogado = servico_equipes.criar_convite(sem_contexto, "b@x.io", cargo, AGORA)
    servico_equipes.revogar_convite(sem_contexto, revogado_id, AGORA)
    pessoa = servico_equipes.identificar(sem_contexto, "sub-z", "Z", None, AGORA)

    # act / assert
    with pytest.raises(ValorInvalido, match="expirou"):
        servico_equipes.aceitar_convite(sem_contexto, velho, pessoa.id, AGORA + timedelta(days=8))
    with pytest.raises(ValorInvalido, match="revogado"):
        servico_equipes.aceitar_convite(sem_contexto, revogado, pessoa.id, AGORA)
    with pytest.raises(NaoEncontrado):
        servico_equipes.aceitar_convite(sem_contexto, "token-que-nao-existe", pessoa.id, AGORA)


def test_convite_com_email_invalido_e_recusado(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)

    # act / assert
    with pytest.raises(ValorInvalido):
        servico_equipes.criar_convite(
            sem_contexto, "sem-arroba", _cargo(sem_contexto, "Técnico"), AGORA
        )


def test_so_convites_pendentes_aparecem_na_lista(sem_contexto: Conexao):
    # arrange
    _equipe_com_admin(sem_contexto)
    cargo = _cargo(sem_contexto, "Técnico")
    servico_equipes.criar_convite(sem_contexto, "pendente@x.io", cargo, AGORA)
    revogado, _ = servico_equipes.criar_convite(sem_contexto, "revogado@x.io", cargo, AGORA)
    servico_equipes.revogar_convite(sem_contexto, revogado, AGORA)

    # act / assert
    assert [c.email for c in servico_equipes.listar_convites(sem_contexto)] == ["pendente@x.io"]


# --- termos (LGPD) ---


def test_termos_pendentes_ate_aceitar_e_voltam_quando_a_versao_muda(
    sem_contexto: Conexao, monkeypatch
):
    # arrange
    pessoa = servico_equipes.identificar(sem_contexto, "sub-t", "T", None, AGORA).id
    assert set(servico_equipes.termos_pendentes(sem_contexto, pessoa)) == {"termos", "privacidade"}

    # act
    servico_equipes.aceitar_termos(sem_contexto, pessoa, AGORA)

    # assert
    assert servico_equipes.termos_pendentes(sem_contexto, pessoa) == ()
    from forms.infra import legal

    monkeypatch.setattr(
        legal, "vigentes", lambda pasta=None: {"termos": "2027-01-01", "privacidade": "2026-11-03"}
    )
    assert servico_equipes.termos_pendentes(sem_contexto, pessoa) == ("termos",)


def test_aceitar_duas_vezes_nao_duplica_o_registro_do_aceite(sem_contexto: Conexao):
    # arrange
    pessoa = servico_equipes.identificar(sem_contexto, "sub-d", "D", None, AGORA).id

    # act
    servico_equipes.aceitar_termos(sem_contexto, pessoa, AGORA)
    servico_equipes.aceitar_termos(sem_contexto, pessoa, AGORA)

    # assert
    assert len(servico_equipes.meus_consentimentos(sem_contexto, pessoa)) == 2


def test_aceitar_documento_inexistente_e_erro(sem_contexto: Conexao):
    # arrange
    pessoa = servico_equipes.identificar(sem_contexto, "sub-e", "E", None, AGORA).id

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico_equipes.aceitar_termos(sem_contexto, pessoa, AGORA, ("cookies",))


# --- primeiro administrador ---


def test_primeiro_administrador_cria_a_equipe_e_o_convite_so_uma_vez(sem_contexto: Conexao):
    # act
    token = servico_equipes.garantir_primeiro_administrador(
        sem_contexto, "adm@x.io", "Minha obra", AGORA
    )
    de_novo = servico_equipes.garantir_primeiro_administrador(
        sem_contexto, "adm@x.io", "Minha obra", AGORA
    )

    # assert: idempotente; o token só existe em claro nessa primeira devolução
    assert token and de_novo is None
    assert repositorio_equipes.contar_grupos(sem_contexto) == 1
    convite = repositorio_equipes.obter_convite_por_hash(
        sem_contexto, segredos.hash_do_token(token)
    )
    assert convite is not None and convite.cargo_nome == "Administrador"
    pessoa = servico_equipes.identificar(sem_contexto, "sub-adm", "Adm", "adm@x.io", AGORA)
    equipe = servico_equipes.aceitar_convite(sem_contexto, token, pessoa.id, AGORA)
    assert servico_equipes.contexto_da_pessoa(sem_contexto, pessoa.id, equipe.id).tem(
        "cargos:editar"
    )


def test_convite_e_aceito_no_papel_do_aplicativo_mesmo_sem_equipe_declarada(
    sem_contexto: Conexao, dsn: str
):
    # arrange: o convite existe; quem aceita ainda não tem equipe (contexto sem `grupo_id`)
    token = servico_equipes.garantir_primeiro_administrador(
        sem_contexto, "adm@x.io", "Minha obra", AGORA
    )
    pessoa = servico_equipes.identificar(sem_contexto, "sub-adm", "Adm", "adm@x.io", AGORA)
    app = banco.abrir_conexao(dsn)
    app.execute("SET ROLE forms_app")  # o superusuário ignoraria o Row Level Security
    app.definir_contexto(Contexto(None, pessoa.id))

    # act: `cargos` tem RLS; um JOIN comum com ele faria o convite "sumir" para esse papel
    equipe = servico_equipes.aceitar_convite(app, token, pessoa.id, AGORA)

    # assert
    assert equipe.nome == "Minha obra"
    app.execute("RESET ROLE")
    app.close()


def test_equipe_e_cargo_da_pessoa_sao_lidos_no_papel_do_aplicativo(sem_contexto: Conexao, dsn: str):
    # arrange: pessoa membro; a conexão do app ainda não declarou equipe (início da requisição)
    token = servico_equipes.garantir_primeiro_administrador(
        sem_contexto, "adm@x.io", "Minha obra", AGORA
    )
    pessoa = servico_equipes.identificar(sem_contexto, "sub-adm", "Adm", "adm@x.io", AGORA)
    equipe = servico_equipes.aceitar_convite(sem_contexto, token, pessoa.id, AGORA)
    app = banco.abrir_conexao(dsn)
    app.execute("SET ROLE forms_app")
    app.definir_contexto(Contexto(None, pessoa.id))

    # act
    contexto = servico_equipes.contexto_da_pessoa(app, pessoa.id, equipe.id)
    minhas = servico_equipes.minhas_equipes(app, pessoa.id)
    nome_do_cargo, permissoes = servico_equipes.cargo_e_permissoes(
        app, minhas[0].cargo_id, equipe.id
    )

    # assert: `cargos` tem RLS; sem declarar a equipe o cargo "sumiria" e a pessoa seria barrada
    assert contexto.tem("cargos:editar")
    assert nome_do_cargo == "Administrador" and "cargos:editar" in permissoes
    assert app.contexto is not None and app.contexto.grupo_id is None  # voltou ao que era
    app.execute("RESET ROLE")
    app.close()


def test_pessoa_sem_nome_no_logto_usa_a_parte_local_do_email(sem_contexto: Conexao):
    # act
    pessoa = servico_equipes.identificar(
        sem_contexto, "sub-x", None, "maria.souza@exemplo.com", AGORA
    )

    # assert
    assert pessoa.nome == "Maria Souza"


def test_pessoa_sem_nome_e_sem_email_continua_com_o_nome_generico(sem_contexto: Conexao):
    # act
    pessoa = servico_equipes.identificar(sem_contexto, "sub-y", None, None, AGORA)

    # assert
    assert pessoa.nome == "Pessoa sem nome"
