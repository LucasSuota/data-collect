"""Segredos (AGENTS.md §12): hash do que só se confere, cifra do que se reutiliza."""

import pytest

from forms.infra import segredos
from forms.infra.segredos import Cifra, SegredoIndisponivel


def test_token_novo_tem_256_bits_e_nunca_se_repete():
    # act
    tokens = {segredos.novo_token() for _ in range(200)}

    # assert: 32 bytes em base64 url-safe têm 43 caracteres
    assert len(tokens) == 200 and all(len(t) >= 43 for t in tokens)


def test_hash_do_token_e_estavel_hexadecimal_e_nao_revela_o_token():
    # arrange
    token = segredos.novo_token()

    # act
    hash_ = segredos.hash_do_token(token)

    # assert
    assert hash_ == segredos.hash_do_token(token) and len(hash_) == 64
    assert token not in hash_ and hash_ != segredos.hash_do_token(token + "x")


def test_iguais_compara_sem_diferenciar_quem_acertou_mais_caracteres():
    # act / assert
    assert segredos.iguais("abc", "abc") and not segredos.iguais("abc", "abd")
    assert not segredos.iguais("abc", "abcd")


def test_cifra_vai_e_volta_e_o_cifrado_nao_contem_o_texto():
    # arrange
    cifra = Cifra([segredos.nova_chave_mestra()])

    # act
    cifrado = cifra.cifrar("sk-chave-do-llm")

    # assert
    assert "sk-chave" not in cifrado and cifra.decifrar(cifrado) == "sk-chave-do-llm"
    assert cifra.cifrar("sk-chave-do-llm") != cifrado  # cada cifra leva um IV novo


def test_rotacao_da_chave_a_nova_cifra_e_a_antiga_ainda_decifra():
    # arrange
    antiga, nova = segredos.nova_chave_mestra(), segredos.nova_chave_mestra()
    cifrado_antigo = Cifra([antiga]).cifrar("segredo")

    # act
    rotacionada = Cifra([nova, antiga])

    # assert
    assert rotacionada.decifrar(cifrado_antigo) == "segredo"
    assert Cifra([nova]).decifrar(rotacionada.cifrar("outro")) == "outro"


def test_decifrar_com_outra_chave_e_erro_de_dominio():
    # arrange
    cifrado = Cifra([segredos.nova_chave_mestra()]).cifrar("segredo")

    # act / assert
    with pytest.raises(SegredoIndisponivel):
        Cifra([segredos.nova_chave_mestra()]).decifrar(cifrado)


@pytest.mark.parametrize("chaves", [[], ["isso-nao-e-uma-chave-fernet"]])
def test_sem_chave_mestra_ou_com_chave_invalida_nada_e_cifrado(chaves):
    # act / assert
    with pytest.raises(SegredoIndisponivel):
        Cifra(chaves)


def test_repr_da_cifra_nao_vaza_nada():
    # arrange
    chave = segredos.nova_chave_mestra()

    # act / assert
    assert chave not in repr(Cifra([chave]))


def test_cifra_do_ambiente_aceita_varias_chaves_separadas_por_virgula():
    # arrange
    a, b = segredos.nova_chave_mestra(), segredos.nova_chave_mestra()

    # act
    cifra = segredos.cifra_do_ambiente({"FORMS_CHAVE_MESTRA": f" {a} , {b} "})

    # assert
    assert cifra is not None and cifra.decifrar(Cifra([b]).cifrar("x")) == "x"
    assert segredos.cifra_do_ambiente({}) is None
