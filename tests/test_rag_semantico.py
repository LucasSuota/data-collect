import math
import sqlite3
import struct

import pytest

from forms import repositorio
from forms.ia.cliente import ClienteFalso, IaIndisponivel
from forms.rag.chunker import Trecho
from forms.rag.indice import IndiceBm25, ResultadoDeBusca
from forms.rag.responder import MENSAGEM_SEM_RESULTADO, perguntar
from forms.rag.semantico import (
    IndiceHibrido,
    IndiceSemantico,
    carregar_vetores,
    desempacotar,
    empacotar,
    fundir_por_rrf,
    similaridade_de_cosseno,
    texto_para_vetorizar,
)

CURA = Trecho("moldagem.md", "Moldagem > Cura", "Manter o concreto úmido por 7 dias.")
RUPTURA = Trecho("moldagem.md", "Moldagem > Ruptura", "Romper os corpos de prova aos 28 dias.")
SOLO = Trecho("solo.md", "Solo > Coleta", "Coletar a amostra de solo a 1 metro de profundidade.")
TRECHOS = [CURA, RUPTURA, SOLO]

# Espaço de 3 dimensões inventado: cada trecho aponta para um eixo, e as consultas para o que
# "significam". Nada aqui depende de palavras em comum (é o que o BM25 não consegue).
VETORES = {
    texto_para_vetorizar(CURA): [1.0, 0.0, 0.0],
    texto_para_vetorizar(RUPTURA): [0.0, 1.0, 0.0],
    texto_para_vetorizar(SOLO): [0.0, 0.0, 1.0],
    "irrigar a massa fresca": [0.9, 0.1, 0.0],
    "assunto sem nenhuma relação": [0.0, 0.0, 0.0],
}


@pytest.fixture
def conexao():
    conexao = repositorio.abrir_conexao(":memory:")
    yield conexao
    conexao.close()


class ClienteContador(ClienteFalso):
    """Conta quantos textos foram vetorizados, para provar que o que já existe não se refaz."""

    def __init__(self, vetores, modelo="modelo-a"):
        super().__init__([], vetores=vetores)
        self.modelo_de_vetores = modelo
        self.textos_vetorizados: list[str] = []

    def vetorizar(self, textos):
        self.textos_vetorizados.extend(textos)
        return super().vetorizar(textos)


# --- vetor <-> bytes ---


def test_vetor_empacotado_volta_igual():
    # arrange
    vetor = [0.5, -1.25, 3.0]

    # act
    de_volta = desempacotar(empacotar(vetor))

    # assert: 0,5, -1,25 e 3 são exatos em 32 bits
    assert de_volta == vetor


def test_vetor_empacotado_usa_quatro_bytes_por_dimensao_em_ordem_fixa():
    # assert: ordem little-endian fixa, para o banco valer em qualquer máquina
    assert empacotar([1.0]) == struct.pack("<f", 1.0)
    assert len(empacotar([0.0] * 10)) == 40


def test_blob_com_tamanho_invalido_e_recusado():
    # act / assert
    with pytest.raises(ValueError, match="múltiplo de 4"):
        desempacotar(b"abc")


# --- similaridade de cosseno ---


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0),
        ([1.0, 0.0], [0.0, 1.0], 0.0),
        ([1.0, 0.0], [-1.0, 0.0], -1.0),
        ([1.0, 1.0], [1.0, 0.0], math.sqrt(2) / 2),
        ([2.0, 0.0], [5.0, 0.0], 1.0),  # só o ângulo importa, não o tamanho
    ],
)
def test_cosseno(a, b, esperado):
    assert similaridade_de_cosseno(a, b) == pytest.approx(esperado)


def test_cosseno_com_vetor_nulo_e_zero_e_nao_divide_por_zero():
    assert similaridade_de_cosseno([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_cosseno_com_dimensoes_diferentes_e_erro():
    with pytest.raises(ValueError, match="dimensões"):
        similaridade_de_cosseno([1.0], [1.0, 2.0])


# --- índice semântico ---


def test_indice_semantico_ordena_pelo_cosseno_e_acha_sem_palavra_em_comum():
    # arrange
    indice = IndiceSemantico(TRECHOS, [VETORES[texto_para_vetorizar(t)] for t in TRECHOS])

    # act: o vetor da consulta aponta para a cura, sem depender de palavra nenhuma
    resultados = indice.buscar([0.9, 0.1, 0.0], k=2, limiar=0.0)

    # assert
    assert [r.trecho for r in resultados] == [CURA, RUPTURA]
    assert resultados[0].pontuacao > resultados[1].pontuacao


def test_indice_semantico_descarta_o_que_esta_abaixo_do_limiar():
    # arrange
    indice = IndiceSemantico(TRECHOS, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    # act: só a cura passa de 0,3; sem limiar, "o vizinho mais próximo" sempre apareceria
    resultados = indice.buscar([0.9, 0.1, 0.0], k=3, limiar=0.3)

    # assert
    assert [r.trecho for r in resultados] == [CURA]


def test_indice_semantico_com_consulta_nula_nao_acha_nada():
    # arrange
    indice = IndiceSemantico(TRECHOS, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    # act / assert
    assert indice.buscar([0.0, 0.0, 0.0], k=3) == []


def test_indice_semantico_exige_um_vetor_por_trecho():
    with pytest.raises(ValueError, match="um vetor por trecho"):
        IndiceSemantico(TRECHOS, [[1.0, 0.0, 0.0]])


# --- vetores guardados no SQLite ---


def test_vetores_sao_guardados_e_nao_se_vetoriza_de_novo(conexao):
    # arrange
    cliente = ClienteContador(VETORES)

    # act
    primeira = carregar_vetores(conexao, cliente, TRECHOS)
    segunda = carregar_vetores(conexao, cliente, TRECHOS)

    # assert
    assert primeira == segunda == [VETORES[texto_para_vetorizar(t)] for t in TRECHOS]
    assert len(cliente.textos_vetorizados) == 3  # só na primeira vez
    assert conexao.execute("SELECT COUNT(*) FROM vetores_trechos").fetchone()[0] == 3


def test_so_o_trecho_novo_ou_alterado_e_vetorizado(conexao):
    # arrange
    cliente = ClienteContador(VETORES)
    carregar_vetores(conexao, cliente, [CURA, RUPTURA])
    cliente.textos_vetorizados.clear()

    # act
    carregar_vetores(conexao, cliente, [CURA, RUPTURA, SOLO])

    # assert
    assert cliente.textos_vetorizados == [texto_para_vetorizar(SOLO)]


def test_vetor_de_trecho_que_saiu_da_base_e_apagado(conexao):
    # arrange
    cliente = ClienteContador(VETORES)
    carregar_vetores(conexao, cliente, TRECHOS)

    # act
    carregar_vetores(conexao, cliente, [CURA])

    # assert
    assert conexao.execute("SELECT COUNT(*) FROM vetores_trechos").fetchone()[0] == 1


def test_trocar_o_modelo_de_embeddings_refaz_os_vetores(conexao):
    # arrange: o mesmo texto vetorizado por outro modelo cai em outro espaço
    antigo = ClienteContador(VETORES, modelo="modelo-a")
    carregar_vetores(conexao, antigo, TRECHOS)
    novo = ClienteContador(VETORES, modelo="modelo-b")

    # act
    carregar_vetores(conexao, novo, TRECHOS)

    # assert
    assert len(novo.textos_vetorizados) == 3
    assert conexao.execute("SELECT COUNT(*) FROM vetores_trechos").fetchone()[0] == 3


def test_vetorizacao_parcial_nao_deixa_lixo_no_banco(conexao):
    # arrange: o provedor cai no meio
    class Quebrado(ClienteContador):
        def vetorizar(self, textos):
            raise IaIndisponivel("sem internet")

    # act / assert
    with pytest.raises(IaIndisponivel):
        carregar_vetores(conexao, Quebrado(VETORES), TRECHOS)
    assert conexao.execute("SELECT COUNT(*) FROM vetores_trechos").fetchone()[0] == 0


def test_provedor_que_devolve_quantidade_errada_de_vetores_e_rejeitado(conexao):
    # arrange: saída do provedor é dado não confiável
    class Torto(ClienteContador):
        def vetorizar(self, textos):
            return [[1.0, 0.0]]

    # act / assert
    with pytest.raises(IaIndisponivel, match="vetores"):
        carregar_vetores(conexao, Torto(VETORES), TRECHOS)


def test_provedor_que_devolve_vetor_invalido_e_rejeitado(conexao):
    # arrange
    class Invalido(ClienteContador):
        def vetorizar(self, textos):
            return [[float("nan"), 0.0]] * len(textos)

    # act / assert
    with pytest.raises(IaIndisponivel, match="vetores"):
        carregar_vetores(conexao, Invalido(VETORES), TRECHOS)


def test_cliente_sem_modelo_de_embeddings_nao_vetoriza(conexao):
    # arrange: ClienteFalso padrão não declara modelo
    cliente = ClienteFalso([], vetores=VETORES)

    # act / assert
    with pytest.raises(IaIndisponivel):
        carregar_vetores(conexao, cliente, TRECHOS)


# --- fusão por rank (RRF) ---


def _r(trecho: Trecho, pontuacao: float = 1.0) -> ResultadoDeBusca:
    return ResultadoDeBusca(trecho, pontuacao)


def test_rrf_premia_o_trecho_que_aparece_nas_duas_listas():
    # arrange: CURA é 2º no BM25 e 1º no semântico; RUPTURA é 1º só no BM25
    bm25 = [_r(RUPTURA), _r(CURA)]
    semantico = [_r(CURA), _r(SOLO)]

    # act
    fundidos = fundir_por_rrf([bm25, semantico], k=3)

    # assert
    assert [r.trecho for r in fundidos] == [CURA, RUPTURA, SOLO]


def test_rrf_usa_a_formula_1_sobre_constante_mais_posicao():
    # arrange
    lista = [_r(CURA), _r(RUPTURA)]

    # act
    fundidos = fundir_por_rrf([lista], k=2, constante=60)

    # assert: 1/(60+1) e 1/(60+2)
    assert [r.pontuacao for r in fundidos] == pytest.approx([1 / 61, 1 / 62])


def test_rrf_respeita_k_e_desempata_pela_ordem_da_primeira_lista():
    # arrange: ocupam posições simétricas, então empatam
    a = [_r(CURA), _r(RUPTURA)]
    b = [_r(RUPTURA), _r(CURA)]

    # act
    fundidos = fundir_por_rrf([a, b], k=1)

    # assert
    assert [r.trecho for r in fundidos] == [CURA]


def test_rrf_sem_listas_ou_com_listas_vazias_nao_devolve_nada():
    assert fundir_por_rrf([], k=3) == []
    assert fundir_por_rrf([[], []], k=3) == []


# --- índice híbrido ---


def _hibrido(conexao, cliente):
    vetores = carregar_vetores(conexao, cliente, TRECHOS)
    return IndiceHibrido(IndiceBm25(TRECHOS), IndiceSemantico(TRECHOS, vetores), cliente)


def test_hibrido_acha_pelo_significado_quando_o_bm25_nao_acha(conexao):
    # arrange: nenhuma palavra da consulta aparece nos trechos
    cliente = ClienteContador(VETORES)
    consulta = "irrigar a massa fresca"

    # act
    sozinho = IndiceBm25(TRECHOS).buscar(consulta, 3)
    junto = _hibrido(conexao, cliente).buscar(consulta, 3)

    # assert
    assert sozinho == []
    assert [r.trecho for r in junto] == [CURA]


def test_hibrido_mantem_o_bm25_quando_os_embeddings_ficam_indisponiveis(conexao):
    # arrange: os vetores dos trechos já estavam no banco, mas a consulta não pode ser vetorizada
    cliente = ClienteContador(VETORES)
    indice = _hibrido(conexao, cliente)

    def sem_internet(textos):
        raise IaIndisponivel("sem internet")

    cliente.vetorizar = sem_internet

    # act
    resultados = indice.buscar("corpos de prova aos 28 dias", 3)

    # assert: cai no BM25 puro, com as mesmas pontuações
    assert resultados == IndiceBm25(TRECHOS).buscar("corpos de prova aos 28 dias", 3)
    assert resultados[0].trecho == RUPTURA


def test_hibrido_sem_resultado_em_nenhum_dos_dois_nao_acha_nada(conexao):
    # arrange
    indice = _hibrido(conexao, ClienteContador(VETORES))

    # act / assert: sem palavras em comum e vetor nulo
    assert indice.buscar("assunto sem nenhuma relação", 3) == []


def test_perguntar_aceita_o_indice_hibrido_e_mantem_o_aviso_de_sem_base(conexao):
    # arrange
    indice = _hibrido(conexao, ClienteContador(VETORES))
    llm = ClienteFalso([])

    # act
    resposta = perguntar(indice, "assunto sem nenhuma relação", llm)

    # assert: sem trecho, não chama o LLM
    assert resposta.encontrou is False
    assert resposta.texto == MENSAGEM_SEM_RESULTADO
    assert llm.chamadas == []


def test_perguntar_com_indice_hibrido_responde_com_o_trecho_achado_pelo_significado(conexao):
    # arrange
    indice = _hibrido(conexao, ClienteContador(VETORES))
    llm = ClienteFalso(["Manter úmido por 7 dias (moldagem.md)."])

    # act
    resposta = perguntar(indice, "irrigar a massa fresca", llm)

    # assert
    assert resposta.encontrou is True
    assert resposta.trechos[0].trecho == CURA


def test_vetores_ficam_no_banco_como_blob(conexao):
    # arrange / act
    carregar_vetores(conexao, ClienteContador(VETORES), [CURA])

    # assert
    linha = conexao.execute("SELECT chave, vetor FROM vetores_trechos").fetchone()
    assert isinstance(linha["vetor"], bytes) and len(linha["vetor"]) == 12
    assert len(linha["chave"]) == 64  # sha256 em hexadecimal


def test_repositorio_de_vetores_guarda_lista_e_apaga(conexao: sqlite3.Connection):
    # act
    repositorio.guardar_vetores(conexao, {"a": b"\x00\x00\x80?", "b": b"\x00\x00\x00@"})
    repositorio.guardar_vetores(conexao, {"a": b"\x00\x00\x00A"})  # substitui
    repositorio.apagar_vetores(conexao, ["b"])

    # assert
    assert repositorio.listar_vetores(conexao) == {"a": b"\x00\x00\x00A"}
