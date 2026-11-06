"""RBAC e isolamento entre equipes, rota por rota (AGENTS.md §2.13, §8).

Dois testes de varredura: um percorre a matriz inteira (cada permissão contra cada endpoint que
ela protege) e outro tenta, com o token de uma equipe, abrir o que é de outra pelo `id`.
"""

import re

from fastapi.testclient import TestClient

from conftest import cliente_da_pessoa, criar_pessoa_na_equipe
from forms.api.matriz_permissoes import (
    PERMISSAO_DA_ROTA,
    PUBLICAS,
    QUALQUER_MEMBRO,
    SEM_EQUIPE,
    classificar,
    rotas_do_app,
)

# Rotas que mudam a própria pessoa (sair da equipe, apagar a conta): testadas à parte.
DESTRUTIVAS_DA_PROPRIA_PESSOA = {("POST", "/equipe/sair"), ("DELETE", "/eu")}

CORPO = {"definicao": {"campos": [{"id": "obs", "tipo": "texto", "rotulo": "Obs"}]}}


def _caminho(modelo: str, **ids: object) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ids.get(m.group(1), 1)), modelo)


def _chamar(cliente: TestClient, metodo: str, caminho: str, corpo: object | None = None):
    argumentos = {} if corpo is None else {"json": corpo}
    return cliente.request(metodo, caminho, **argumentos)


def _cargo_com(cliente: TestClient, nome: str, permissoes: list[str]) -> int:
    resposta = cliente.post(
        "/cargos", json={"nome": nome, "descricao": "", "permissoes": permissoes}
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


# --- tabela de verdade: permissão x endpoint ---


def test_cada_rota_barra_quem_nao_tem_a_permissao_e_deixa_passar_quem_tem(
    app, chave_privada, cliente, pessoa, dsn
):
    # arrange: uma pessoa sem permissão nenhuma e uma com exatamente cada permissão da matriz
    exigidas = sorted({p for spec in PERMISSAO_DA_ROTA.values() for p in spec.split("|")})
    _cargo_com(cliente, "Nada", [])
    sem_nada = cliente_da_pessoa(
        app, chave_privada, criar_pessoa_na_equipe(dsn, "nada", "Nada", int(pessoa["grupo_id"]))
    )
    so_com = {}
    for permissao in exigidas:
        nome = f"So {permissao}"
        _cargo_com(cliente, nome, [permissao])
        so_com[permissao] = cliente_da_pessoa(
            app,
            chave_privada,
            criar_pessoa_na_equipe(dsn, permissao.replace(":", "_"), nome, int(pessoa["grupo_id"])),
        )

    # act
    erradas = []
    for rota in sorted(rotas_do_app(app)):
        classe = classificar(rota)
        if classe in {"publica", "sem_equipe", "negada"} or rota in DESTRUTIVAS_DA_PROPRIA_PESSOA:
            continue
        caminho = _caminho(rota[1])
        if classe == "qualquer_membro":
            resposta = _chamar(sem_nada, rota[0], caminho, {})
            if resposta.status_code in {401, 403}:
                erradas.append((rota, "qualquer membro foi barrado", resposta.status_code))
            continue
        barrado = _chamar(sem_nada, rota[0], caminho, {})
        if barrado.status_code != 403 or barrado.json().get("codigo") != "sem_permissao":
            erradas.append((rota, "sem permissão não foi barrado", barrado.status_code))
        for permissao in classe.split("|"):
            passou = _chamar(so_com[permissao], rota[0], caminho, {})
            if passou.status_code == 403:
                erradas.append((rota, f"{permissao} foi barrada", passou.text))

    # assert
    assert erradas == []


def test_matriz_so_cita_permissoes_que_existem_e_nao_repete_rota(app):
    # arrange
    from forms.dominio.permissoes import IDS_DE_PERMISSAO

    # act
    citadas = {p for spec in PERMISSAO_DA_ROTA.values() for p in spec.split("|")}

    # assert
    assert citadas <= IDS_DE_PERMISSAO
    assert QUALQUER_MEMBRO & set(PERMISSAO_DA_ROTA) == set()
    assert (PUBLICAS | SEM_EQUIPE) & set(PERMISSAO_DA_ROTA) == set()
    # as rotas do núcleo (sem as extensões opcionais de IA) estão todas decididas
    assert all(classificar(rota) != "negada" for rota in rotas_do_app(app))


def test_o_administrador_tem_acesso_a_toda_rota_de_dados(cliente, app):
    # act
    barradas = [
        rota
        for rota in rotas_do_app(app)
        if classificar(rota) not in {"publica", "negada", "sem_equipe"}
        and rota not in DESTRUTIVAS_DA_PROPRIA_PESSOA
        and _chamar(cliente, rota[0], _caminho(rota[1]), {}).status_code == 403
    ]

    # assert
    assert barradas == []


# --- isolamento: o que é da equipe A, a equipe B não alcança (404, nunca 403 nem 200) ---


def _preparar_a(cliente: TestClient) -> dict[str, int]:
    formulario = cliente.post("/formularios", json={"nome": "ensaio", **CORPO}).json()
    versao = formulario["versao_atual"]["id"]
    registro = cliente.post(
        f"/formularios/{formulario['id']}/registros",
        json={"versao_id": versao, "dados": {"obs": "x"}},
    ).json()
    pasta = cliente.post("/pastas", json={"nome": "Lab"}).json()
    cargo = _cargo_com(cliente, "Só da A", ["registros:ver"])
    convite = cliente.post("/convites", json={"email": "a@x.io", "cargo_id": cargo}).json()[
        "convite"
    ]
    return {
        "formulario_id": formulario["id"],
        "versao_id": versao,
        "registro_id": registro["id"],
        "pasta_id": pasta["id"],
        "cargo_id": cargo,
        "convite_id": convite["id"],
        "usuario_id": 1,
    }


def _corpos(ids: dict[str, int], cargo_da_b: int) -> dict[tuple[str, str], object]:
    return {
        ("PUT", "/formularios/{formulario_id}/pasta"): {"pasta_id": None},
        ("POST", "/formularios/{formulario_id}/versoes"): CORPO,
        ("POST", "/formularios/{formulario_id}/registros"): {
            "versao_id": ids["versao_id"],
            "dados": {},
        },
        ("PUT", "/pastas/{pasta_id}"): {"nome": "x", "pasta_pai_id": None},
        ("PUT", "/registros/{registro_id}"): {"dados": {}, "revisao": 1},
        ("PUT", "/cargos/{cargo_id}"): {"nome": "x", "descricao": "", "permissoes": []},
        ("PUT", "/membros/{usuario_id}/cargo"): {"cargo_id": cargo_da_b},
        ("PUT", "/formularios/{formulario_id}/rascunho"): CORPO,
        ("POST", "/formularios/{formulario_id}/rascunho/publicar"): None,
    }


def test_equipe_b_nao_alcanca_nenhum_recurso_da_equipe_a_pelo_id(app, chave_privada, cliente, dsn):
    # arrange
    ids = _preparar_a(cliente)
    pessoa_b = criar_pessoa_na_equipe(dsn, "bia")
    cliente_b = cliente_da_pessoa(app, chave_privada, pessoa_b)
    cargo_da_b = next(c["id"] for c in cliente_b.get("/cargos").json() if c["nome"] == "Gestor")
    corpos = _corpos(ids, cargo_da_b)

    # act
    vazaram, cobertas = [], []
    for rota in sorted(rotas_do_app(app)):
        if "{" not in rota[1] or classificar(rota) in {"publica", "sem_equipe"}:
            continue
        resposta = _chamar(cliente_b, rota[0], _caminho(rota[1], **ids), corpos.get(rota))
        cobertas.append(rota)
        if resposta.status_code != 404:
            vazaram.append((rota, resposta.status_code, resposta.text[:120]))

    # assert: nenhuma rota com id respondeu algo diferente de "não existe"
    assert vazaram == []
    assert len(cobertas) >= 20


def test_a_lista_de_cada_equipe_mostra_so_o_que_e_dela(app, chave_privada, cliente, dsn):
    # arrange
    _preparar_a(cliente)
    cliente_b = cliente_da_pessoa(app, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))

    # act / assert
    assert cliente_b.get("/formularios").json() == []
    assert cliente_b.get("/pastas").json() == []
    assert "Só da A" not in {c["nome"] for c in cliente_b.get("/cargos").json()}
    assert cliente_b.get("/convites").json() == []
    assert cliente_b.get("/membros").json()[0]["nome"] == "bia"


def test_mesmo_nome_de_formulario_em_duas_equipes_e_permitido(app, chave_privada, cliente, dsn):
    # arrange
    cliente_b = cliente_da_pessoa(app, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))

    # act
    a = cliente.post("/formularios", json={"nome": "ensaio", **CORPO})
    b = cliente_b.post("/formularios", json={"nome": "ensaio", **CORPO})

    # assert
    assert a.status_code == 201 and b.status_code == 201


def test_referencia_a_formulario_de_outra_equipe_e_rejeitada(app, chave_privada, cliente, dsn):
    # arrange: o formulário "ensaio" só existe na equipe A
    cliente.post("/formularios", json={"nome": "ensaio", **CORPO})
    cliente_b = cliente_da_pessoa(app, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))
    dependente = {
        "campos": [{"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"}]
    }

    # act
    resposta = cliente_b.post("/formularios", json={"nome": "proctor", "definicao": dependente})

    # assert
    assert resposta.status_code == 422 and "não existe" in resposta.json()["erros"][0]["mensagem"]


def test_registro_nao_pode_apontar_para_registro_de_outra_equipe(app, chave_privada, cliente, dsn):
    # arrange: B tem um formulário "ensaio" próprio; o registro 1 da A não é dele
    ids = _preparar_a(cliente)
    cliente_b = cliente_da_pessoa(app, chave_privada, criar_pessoa_na_equipe(dsn, "bia"))
    cliente_b.post("/formularios", json={"nome": "ensaio", **CORPO})
    dependente = {
        "campos": [{"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"}]
    }
    f = cliente_b.post("/formularios", json={"nome": "proctor", "definicao": dependente}).json()

    # act
    resposta = cliente_b.post(
        f"/formularios/{f['id']}/registros",
        json={"versao_id": f["versao_atual"]["id"], "dados": {"e": ids["registro_id"]}},
    )

    # assert
    assert resposta.status_code == 422
