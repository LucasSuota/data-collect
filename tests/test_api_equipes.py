"""Pessoa, equipe, cargos, convites e termos pela API (AGENTS.md §2.12 a §2.15)."""

from fastapi.testclient import TestClient

from conftest import cliente_da_pessoa, criar_pessoa_na_equipe, emitir_token

ADMIN = "Administrador"


def _cargo(cliente: TestClient, nome: str) -> int:
    return next(c["id"] for c in cliente.get("/cargos").json() if c["nome"] == nome)


# --- eu ---


def test_eu_devolve_perfil_equipes_com_cargo_e_permissoes(cliente, pessoa):
    # act
    eu = cliente.get("/eu").json()

    # assert
    assert eu["pessoa"]["nome"] == "ana" and eu["termos_pendentes"] == []
    equipe = eu["equipes"][0]
    assert equipe["id"] == pessoa["grupo_id"] and equipe["cargo"]["nome"] == ADMIN
    assert len(equipe["permissoes"]) == 17 and equipe["ativa"] is True


def test_eu_nao_exige_o_cabecalho_de_equipe(app, chave_privada, pessoa):
    # arrange
    sem_equipe = TestClient(
        app, headers={"Authorization": f"Bearer {emitir_token(chave_privada, str(pessoa['sub']))}"}
    )

    # act / assert
    assert sem_equipe.get("/eu").status_code == 200


def test_pessoa_em_duas_equipes_precisa_dizer_qual(app, chave_privada, pessoa, dsn):
    # arrange: a mesma pessoa entra numa segunda equipe
    outra = criar_pessoa_na_equipe(dsn, "outra-equipe")
    from forms import banco, servico_equipes

    con = banco.abrir_conexao(dsn)
    usuario = servico_equipes.repositorio_equipes.obter_usuario_por_sub(con, str(pessoa["sub"]))
    cargo = con.execute("SELECT id FROM cargos WHERE grupo_id = %s LIMIT 1", (outra["grupo_id"],))
    servico_equipes.repositorio_equipes.adicionar_membro(
        con,
        int(outra["grupo_id"]),
        usuario.id,
        cargo.fetchone()["id"],
        usuario.criado_em
        and __import__("datetime").datetime(2026, 11, 2, tzinfo=__import__("datetime").UTC),
    )
    con.close()
    token = emitir_token(chave_privada, str(pessoa["sub"]))

    # act
    sem_dizer = TestClient(app, headers={"Authorization": f"Bearer {token}"}).get("/formularios")
    dizendo = TestClient(
        app, headers={"Authorization": f"Bearer {token}", "X-Equipe": str(pessoa["grupo_id"])}
    ).get("/formularios")

    # assert
    assert sem_dizer.status_code == 422 and "X-Equipe" in sem_dizer.json()["detalhe"]
    assert dizendo.status_code == 200


# --- documentos legais e consentimento ---


def test_documentos_legais_sao_publicos_e_trazem_a_versao(app):
    # act
    corpo = TestClient(app).get("/legal").json()

    # assert
    assert [d["id"] for d in corpo["documentos"]] == ["termos", "privacidade"]
    assert all(d["versao"] and d["markdown"].startswith("# ") for d in corpo["documentos"])


def test_documento_legal_inexistente_e_404(app):
    # act / assert
    assert TestClient(app).get("/legal/cookies").status_code == 404


def test_consentimentos_listam_o_que_foi_aceito_e_o_que_falta(cliente):
    # act
    corpo = cliente.get("/consentimentos").json()

    # assert
    assert {a["documento"] for a in corpo["aceites"]} == {"termos", "privacidade"}
    assert corpo["pendentes"] == []


def test_catalogo_de_permissoes_traz_as_17_com_grupo_e_descricao(app):
    # act
    permissoes = TestClient(app).get("/catalogo/permissoes").json()["permissoes"]

    # assert
    assert len(permissoes) == 17
    assert {p["grupo"] for p in permissoes} == {
        "Formulários",
        "Registros",
        "Inteligência artificial",
        "Equipe e sistema",
    }
    assert all(p["rotulo"] and p["descricao"] for p in permissoes)


# --- cargos ---


def test_listar_cargos_traz_os_de_partida_com_a_contagem_de_pessoas(cliente):
    # act
    cargos = {c["nome"]: c for c in cliente.get("/cargos").json()}

    # assert
    assert set(cargos) == {ADMIN, "Gestor", "Engenheiro", "Técnico", "Visualizador"}
    assert cargos[ADMIN]["pessoas"] == 1 and cargos["Gestor"]["pessoas"] == 0
    assert len(cargos["Engenheiro"]["permissoes"]) == 11


def test_criar_editar_e_excluir_cargo(cliente):
    # act
    criado = cliente.post(
        "/cargos", json={"nome": "Supervisor", "descricao": "d", "permissoes": ["registros:ver"]}
    )
    editado = cliente.put(
        f"/cargos/{criado.json()['id']}",
        json={
            "nome": "Supervisor 2",
            "descricao": "",
            "permissoes": ["registros:ver", "equipe:ver"],
        },
    )
    excluido = cliente.delete(f"/cargos/{criado.json()['id']}")

    # assert
    assert criado.status_code == 201 and editado.json()["permissoes"] == [
        "equipe:ver",
        "registros:ver",
    ]
    assert excluido.status_code == 204


def test_cargo_com_permissao_inexistente_ou_nome_repetido_e_422_com_o_campo(cliente):
    # act
    inexistente = cliente.post(
        "/cargos", json={"nome": "X", "descricao": "", "permissoes": ["a:b"]}
    )
    repetido = cliente.post("/cargos", json={"nome": ADMIN, "descricao": "", "permissoes": []})

    # assert
    assert (
        inexistente.status_code == 422 and inexistente.json()["erros"][0]["campo"] == "permissoes"
    )
    assert repetido.status_code == 422 and repetido.json()["erros"][0]["campo"] == "nome"


def test_cargo_em_uso_nao_e_excluido(cliente):
    # act
    resposta = cliente.delete(f"/cargos/{_cargo(cliente, ADMIN)}")

    # assert
    assert resposta.status_code == 422 and "pessoas" in resposta.json()["erros"][0]["mensagem"]


def test_unico_administrador_nao_perde_o_cargo_pela_api(cliente, pessoa):
    # act
    rebaixar = cliente.put(
        f"/membros/{pessoa['usuario_id']}/cargo", json={"cargo_id": _cargo(cliente, "Gestor")}
    )
    desativar = cliente.post(f"/membros/{pessoa['usuario_id']}/desativar")
    sair = cliente.post("/equipe/sair")

    # assert
    assert {rebaixar.status_code, desativar.status_code, sair.status_code} == {422}
    assert cliente.get("/cargos").status_code == 200


def test_cargo_so_leitura_nao_cria_cargo_nem_ve_convites(app, chave_privada, cliente, pessoa, dsn):
    # arrange
    visualizador = cliente_da_pessoa(
        app,
        chave_privada,
        criar_pessoa_na_equipe(dsn, "vis", "Visualizador", int(pessoa["grupo_id"])),
    )

    # act / assert
    assert (
        visualizador.post(
            "/cargos", json={"nome": "X", "descricao": "", "permissoes": []}
        ).status_code
        == 403
    )
    assert visualizador.get("/convites").status_code == 403
    assert visualizador.get("/membros").status_code == 403  # Visualizador não vê a equipe


# --- equipe e membros ---


def test_renomear_a_equipe_e_listar_membros(cliente):
    # act
    renomeada = cliente.put("/equipe", json={"nome": "Obra do Centro"})
    membros = cliente.get("/membros").json()

    # assert
    assert renomeada.json()["nome"] == "Obra do Centro" == cliente.get("/equipe").json()["nome"]
    assert [(m["nome"], m["cargo"]["nome"], m["ativo"]) for m in membros] == [("ana", ADMIN, True)]


def test_mudar_cargo_desativar_e_reativar_uma_pessoa(app, chave_privada, cliente, pessoa, dsn):
    # arrange
    colega = criar_pessoa_na_equipe(dsn, "colega", "Visualizador", int(pessoa["grupo_id"]))
    do_colega = cliente_da_pessoa(app, chave_privada, colega)
    assert do_colega.get("/formularios").status_code == 200

    # act
    promovida = cliente.put(
        f"/membros/{colega['usuario_id']}/cargo", json={"cargo_id": _cargo(cliente, "Gestor")}
    )
    desativada = cliente.post(f"/membros/{colega['usuario_id']}/desativar")
    bloqueada = do_colega.get("/formularios")
    reativada = cliente.post(f"/membros/{colega['usuario_id']}/reativar")

    # assert
    assert (promovida.status_code, desativada.status_code, reativada.status_code) == (204, 204, 204)
    assert bloqueada.status_code == 403 and do_colega.get("/formularios").status_code == 200
    inativos = [m for m in cliente.get("/membros").json() if not m["ativo"]]
    assert inativos == []


# --- convites: o fluxo inteiro ---


def test_convite_do_envio_ao_primeiro_acesso_da_pessoa_nova(app, chave_privada, cliente, pessoa):
    # arrange: a pessoa nova já tem conta no Logto, mas ainda nenhuma equipe
    nova = TestClient(
        app, headers={"Authorization": f"Bearer {emitir_token(chave_privada, 'sub-nova-no-logto')}"}
    )
    assert nova.get("/formularios").status_code == 403

    # act: o administrador convida; a pessoa aceita o link e aceita os termos
    convite = cliente.post(
        "/convites", json={"email": "nova@x.io", "cargo_id": _cargo(cliente, "Técnico")}
    )
    token = convite.json()["token"]
    aceitou = nova.post(f"/convites/{token}/aceitar")
    pendentes = nova.get("/eu").json()["termos_pendentes"]
    nova.post("/consentimentos", json={})
    com_equipe = TestClient(
        app,
        headers={**nova.headers, "X-Equipe": str(pessoa["grupo_id"])},
    )

    # assert
    assert convite.status_code == 201 and aceitou.json()["equipe"]["id"] == pessoa["grupo_id"]
    assert sorted(pendentes) == ["privacidade", "termos"]
    assert com_equipe.get("/formularios").status_code == 200
    assert (
        com_equipe.post(
            "/cargos", json={"nome": "x", "descricao": "", "permissoes": []}
        ).status_code
        == 403
    )
    assert cliente.get("/convites").json() == []  # usado, sai da lista de pendentes


def test_token_do_convite_so_aparece_na_criacao(cliente):
    # arrange
    cargo = _cargo(cliente, "Técnico")

    # act
    criado = cliente.post("/convites", json={"email": "a@x.io", "cargo_id": cargo}).json()
    listado = cliente.get("/convites").json()

    # assert
    assert criado["token"] and "token" not in listado[0]
    assert listado[0]["email"] == "a@x.io" and listado[0]["cargo"]["nome"] == "Técnico"


def test_convite_usado_duas_vezes_ou_revogado_e_recusado(app, chave_privada, cliente):
    # arrange
    cargo = _cargo(cliente, "Técnico")
    um = cliente.post("/convites", json={"email": "um@x.io", "cargo_id": cargo}).json()
    dois = cliente.post("/convites", json={"email": "dois@x.io", "cargo_id": cargo}).json()
    pessoa_a = TestClient(
        app, headers={"Authorization": f"Bearer {emitir_token(chave_privada, 'sub-a')}"}
    )
    pessoa_b = TestClient(
        app, headers={"Authorization": f"Bearer {emitir_token(chave_privada, 'sub-b')}"}
    )

    # act
    primeira = pessoa_a.post(f"/convites/{um['token']}/aceitar")
    repetida = pessoa_b.post(f"/convites/{um['token']}/aceitar")
    cliente.delete(f"/convites/{dois['convite']['id']}")
    revogada = pessoa_b.post(f"/convites/{dois['token']}/aceitar")
    inexistente = pessoa_b.post("/convites/token-inventado/aceitar")

    # assert
    assert primeira.status_code == 200
    assert repetida.status_code == 422 and "já foi usado" in repetida.json()["detalhe"]
    assert revogada.status_code == 422 and "revogado" in revogada.json()["detalhe"]
    assert inexistente.status_code == 404


def test_nao_se_convida_para_cargo_mais_poderoso_que_o_proprio(app, chave_privada, cliente, pessoa):
    # arrange: um gerente que convida, mas não é administrador
    cliente.post(
        "/cargos",
        json={"nome": "Gerente", "descricao": "", "permissoes": ["equipe:convidar", "equipe:ver"]},
    )
    from conftest import criar_pessoa_na_equipe as criar  # noqa: PLC0415

    gerente = cliente_da_pessoa(
        app,
        chave_privada,
        criar(app.state.configuracao.dsn, "gerente", "Gerente", int(pessoa["grupo_id"])),
    )

    # act
    resposta = gerente.post(
        "/convites", json={"email": "x@y.io", "cargo_id": _cargo(cliente, ADMIN)}
    )

    # assert
    assert resposta.status_code == 403 and resposta.json()["codigo"] == "sem_permissao"
