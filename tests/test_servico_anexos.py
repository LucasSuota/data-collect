import io
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PIL import Image

from forms import servico
from forms.models import FotoInvalida, NaoEncontrado, RegistroInvalido
from forms.repositorio import abrir_conexao, criar_anexo, obter_anexo

AGORA = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)
DEFINICAO = {
    "campos": [
        {"id": "titulo", "tipo": "texto", "rotulo": "Título"},
        {"id": "fotos", "tipo": "foto", "rotulo": "Fotos", "maximo": 3},
        {"id": "detalhe", "tipo": "foto", "rotulo": "Detalhe"},
    ]
}


@pytest.fixture
def conexao():
    conexao = abrir_conexao(":memory:")
    yield conexao
    conexao.close()


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    return tmp_path / "dados"


@pytest.fixture
def criado(conexao):
    return servico.criar_formulario(conexao, "obra", DEFINICAO, AGORA)


def _imagem(largura=400, altura=300, formato="JPEG") -> bytes:
    gerador = random.Random(largura)
    base = Image.frombytes("RGB", (largura, altura), gerador.randbytes(largura * altura * 3))
    destino = io.BytesIO()
    base.save(destino, formato)
    return destino.getvalue()


def _foto(conexao, pasta, quando=AGORA):
    return servico.guardar_anexo(conexao, pasta, _imagem(), quando)


def _registro(conexao, criado, dados):
    return servico.criar_registro(conexao, criado.formulario.id, criado.versao.id, dados, AGORA)


def _arquivos(pasta: Path) -> list[Path]:
    return sorted((pasta / "anexos").glob("*")) if (pasta / "anexos").exists() else []


# --- guardar e ler ---


def test_guardar_anexo_grava_um_webp_com_nome_gerado_e_os_metadados(conexao, pasta):
    # act
    anexo = _foto(conexao, pasta)

    # assert
    (arquivo,) = _arquivos(pasta)
    assert anexo.caminho == f"anexos/{arquivo.name}" and arquivo.suffix == ".webp"
    assert len(arquivo.stem) == 32  # uuid4 em hexadecimal, nunca o nome enviado
    assert anexo.registro_id is None and anexo.tamanho_bytes == arquivo.stat().st_size
    assert Image.open(arquivo).format == "WEBP"
    assert (anexo.largura, anexo.altura) == Image.open(arquivo).size


def test_cada_envio_gera_um_nome_diferente(conexao, pasta):
    # act
    a, b = _foto(conexao, pasta), _foto(conexao, pasta)

    # assert
    assert a.caminho != b.caminho and len(_arquivos(pasta)) == 2


def test_ler_anexo_devolve_os_bytes_do_webp(conexao, pasta):
    # arrange
    anexo = _foto(conexao, pasta)

    # act
    conteudo = servico.ler_anexo(conexao, pasta, anexo.id)

    # assert
    assert Image.open(io.BytesIO(conteudo)).format == "WEBP"


def test_ler_anexo_inexistente_ou_com_arquivo_sumido_e_nao_encontrado(conexao, pasta):
    # arrange
    anexo = _foto(conexao, pasta)
    _arquivos(pasta)[0].unlink()

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.ler_anexo(conexao, pasta, 999)
    with pytest.raises(NaoEncontrado):
        servico.ler_anexo(conexao, pasta, anexo.id)


def test_ler_anexo_com_caminho_fora_da_pasta_de_dados_e_recusado(conexao, pasta, tmp_path):
    # arrange: um arquivo secreto fora da pasta e um anexo (corrompido) apontando para ele
    (tmp_path / "segredo.txt").write_text("segredo")
    pasta.mkdir()
    conexao.execute(
        "INSERT INTO anexos (caminho, largura, altura, tamanho_bytes, criado_em)"
        " VALUES ('anexos/../../segredo.txt', 1, 1, 1, 'x')"
    )

    # act / assert
    with pytest.raises(NaoEncontrado):
        servico.ler_anexo(conexao, pasta, 1)


def test_imagem_invalida_levanta_foto_invalida_e_nao_deixa_arquivo_nem_linha(conexao, pasta):
    # act
    with pytest.raises(FotoInvalida):
        servico.guardar_anexo(conexao, pasta, b"nao e imagem", AGORA)

    # assert
    assert _arquivos(pasta) == []
    assert conexao.execute("SELECT COUNT(*) FROM anexos").fetchone()[0] == 0


def test_falha_ao_registrar_os_metadados_apaga_o_arquivo(conexao, pasta, monkeypatch):
    # arrange
    def falhar(*argumentos, **nomeados):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(servico.repositorio, "criar_anexo", falhar)

    # act
    with pytest.raises(RuntimeError):
        _foto(conexao, pasta)

    # assert
    assert _arquivos(pasta) == [] and not conexao.in_transaction


# --- vincular, trocar e retirar ---


def test_registro_com_foto_vincula_o_anexo_ao_registro_e_ao_campo(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)

    # act
    registro = _registro(conexao, criado, {"fotos": [anexo.id]})

    # assert
    vinculado = obter_anexo(conexao, anexo.id)
    assert (vinculado.registro_id, vinculado.campo_id) == (registro.id, "fotos")
    assert registro.dados["fotos"] == [anexo.id]


def test_anexo_inexistente_e_erro_no_campo(conexao, criado):
    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, criado, {"fotos": [999]})

    # assert
    assert [e.campo for e in excecao.value.erros] == ["fotos"]


def test_anexo_de_outro_registro_nao_pode_ser_reaproveitado(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)
    _registro(conexao, criado, {"fotos": [anexo.id]})

    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, criado, {"detalhe": [anexo.id]})

    # assert
    assert "já está vinculada" in excecao.value.erros[0].mensagem
    assert obter_anexo(conexao, anexo.id).campo_id == "fotos"


def test_mesmo_anexo_em_dois_campos_do_mesmo_registro_e_erro(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)

    # act / assert
    with pytest.raises(RegistroInvalido):
        _registro(conexao, criado, {"fotos": [anexo.id], "detalhe": [anexo.id]})


def test_erro_de_validacao_nao_vincula_nenhuma_foto(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)

    # act
    with pytest.raises(RegistroInvalido):
        _registro(conexao, criado, {"fotos": [anexo.id], "titulo": 5})

    # assert
    assert obter_anexo(conexao, anexo.id).registro_id is None


def test_registro_pode_manter_as_mesmas_fotos_ao_ser_atualizado(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)
    registro = _registro(conexao, criado, {"fotos": [anexo.id]})

    # act
    servico.atualizar_registro(
        conexao, registro.id, {"fotos": [anexo.id], "titulo": "x"}, AGORA, pasta
    )

    # assert
    assert obter_anexo(conexao, anexo.id).registro_id == registro.id
    assert len(_arquivos(pasta)) == 1


def test_trocar_foto_apaga_a_retirada_e_o_arquivo_dela(conexao, pasta, criado):
    # arrange
    velha, nova = _foto(conexao, pasta), _foto(conexao, pasta)
    registro = _registro(conexao, criado, {"fotos": [velha.id]})

    # act
    servico.atualizar_registro(conexao, registro.id, {"fotos": [nova.id]}, AGORA, pasta)

    # assert
    with pytest.raises(NaoEncontrado):
        obter_anexo(conexao, velha.id)
    assert obter_anexo(conexao, nova.id).registro_id == registro.id
    assert [a.name for a in _arquivos(pasta)] == [Path(nova.caminho).name]


def test_retirar_todas_as_fotos_apaga_anexos_e_arquivos(conexao, pasta, criado):
    # arrange
    a, b = _foto(conexao, pasta), _foto(conexao, pasta)
    registro = _registro(conexao, criado, {"fotos": [a.id], "detalhe": [b.id]})

    # act
    servico.atualizar_registro(conexao, registro.id, {}, AGORA, pasta)

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM anexos").fetchone()[0] == 0
    assert _arquivos(pasta) == []


def test_arquivo_so_e_apagado_depois_do_commit_e_falha_na_transacao_o_preserva(
    conexao, pasta, criado, monkeypatch
):
    # arrange: a foto é retirada, mas a atualização falha antes do commit
    anexo = _foto(conexao, pasta)
    registro = _registro(conexao, criado, {"fotos": [anexo.id]})

    def falhar(*argumentos, **nomeados):
        raise RuntimeError("falha simulada antes do commit")

    monkeypatch.setattr(servico.repositorio, "substituir_referencias", falhar)

    # act
    with pytest.raises(RuntimeError):
        servico.atualizar_registro(conexao, registro.id, {}, AGORA, pasta)

    # assert: a linha e o arquivo continuam, o registro ainda tem a foto
    assert obter_anexo(conexao, anexo.id).registro_id == registro.id
    assert len(_arquivos(pasta)) == 1


def test_foto_acima_do_maximo_do_campo_e_erro(conexao, pasta, criado):
    # arrange
    ids = [_foto(conexao, pasta).id for _ in range(4)]

    # act
    with pytest.raises(RegistroInvalido) as excecao:
        _registro(conexao, criado, {"fotos": ids})

    # assert
    assert "no máximo 3" in excecao.value.erros[0].mensagem


# --- excluir registro ---


def test_excluir_registro_apaga_as_fotos_e_os_arquivos(conexao, pasta, criado):
    # arrange
    anexo = _foto(conexao, pasta)
    registro = _registro(conexao, criado, {"fotos": [anexo.id]})

    # act
    servico.excluir_registro(conexao, registro.id, pasta)

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM anexos").fetchone()[0] == 0
    assert _arquivos(pasta) == []


def test_excluir_registro_bloqueado_nao_toca_nas_fotos(conexao, pasta):
    # arrange: o proctor referencia o ensaio e tem uma foto; o ensaio não pode ser excluído
    ensaio = servico.criar_formulario(conexao, "ensaio", {"campos": []}, AGORA)
    proctor = servico.criar_formulario(
        conexao,
        "proctor",
        {
            "campos": [
                {"id": "e", "tipo": "referencia", "rotulo": "E", "formulario": "ensaio"},
                {"id": "f", "tipo": "foto", "rotulo": "F"},
            ]
        },
        AGORA,
    )
    origem = servico.criar_registro(conexao, ensaio.formulario.id, ensaio.versao.id, {}, AGORA)
    anexo = _foto(conexao, pasta)
    servico.criar_registro(
        conexao, proctor.formulario.id, proctor.versao.id, {"e": origem.id, "f": [anexo.id]}, AGORA
    )

    # act
    with pytest.raises(Exception, match="referenciado"):
        servico.excluir_registro(conexao, origem.id, pasta)

    # assert
    assert len(_arquivos(pasta)) == 1


# --- limpeza de órfãos ---


def test_limpeza_remove_so_os_orfaos_com_mais_de_24h(conexao, pasta, criado):
    # arrange
    velho = _foto(conexao, pasta, AGORA - timedelta(hours=25))
    recente = _foto(conexao, pasta, AGORA - timedelta(hours=23))
    vinculado = _foto(conexao, pasta, AGORA - timedelta(days=30))
    _registro(conexao, criado, {"fotos": [vinculado.id]})

    # act
    removidos = servico.limpar_anexos_orfaos(conexao, pasta, AGORA)

    # assert
    assert removidos == 1
    with pytest.raises(NaoEncontrado):
        obter_anexo(conexao, velho.id)
    assert obter_anexo(conexao, recente.id).id and obter_anexo(conexao, vinculado.id).id
    assert sorted(a.name for a in _arquivos(pasta)) == sorted(
        Path(x.caminho).name for x in (recente, vinculado)
    )


def test_limpeza_sem_orfaos_nao_faz_nada(conexao, pasta):
    # act / assert
    assert servico.limpar_anexos_orfaos(conexao, pasta, AGORA) == 0


def test_limpeza_tolera_arquivo_que_ja_sumiu(conexao, pasta):
    # arrange
    velho = _foto(conexao, pasta, AGORA - timedelta(days=2))
    (pasta / velho.caminho).unlink()

    # act / assert
    assert servico.limpar_anexos_orfaos(conexao, pasta, AGORA) == 1


def test_limpeza_nunca_apaga_arquivo_fora_da_pasta_de_dados(conexao, pasta, tmp_path):
    # arrange: um anexo órfão (corrompido) apontando para fora da pasta
    (tmp_path / "importante.txt").write_text("nao apague")
    pasta.mkdir()
    criar_anexo(
        conexao,
        "anexos/ok.webp",
        largura=1,
        altura=1,
        tamanho_bytes=1,
        agora=AGORA - timedelta(days=2),
    )
    conexao.execute("UPDATE anexos SET caminho = 'anexos/../../importante.txt'")
    conexao.commit()

    # act
    servico.limpar_anexos_orfaos(conexao, pasta, AGORA)

    # assert
    assert (tmp_path / "importante.txt").read_text() == "nao apague"
