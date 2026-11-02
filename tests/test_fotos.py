import io
import random

import pytest
from PIL import Image, ImageCms

from forms import fotos
from forms.fotos import FotoProcessada, processar_foto
from forms.models import ErroDeDominio, FotoInvalida

KB = 1024


def _bytes_da_imagem(imagem: Image.Image, formato: str, **opcoes: object) -> bytes:
    destino = io.BytesIO()
    imagem.save(destino, formato, **opcoes)
    return destino.getvalue()


def _ruido(largura: int, altura: int) -> Image.Image:
    gerador = random.Random(1)
    return Image.frombytes("RGB", (largura, altura), gerador.randbytes(largura * altura * 3))


def _gradiente(largura: int, altura: int) -> Image.Image:
    # `Image.linear_gradient` é cinza 256x256; ampliado e colorido fica liso e fácil de comprimir
    base = Image.linear_gradient("L").resize((largura, altura))
    return Image.merge("RGB", (base, base.transpose(Image.Transpose.FLIP_TOP_BOTTOM), base))


def _abrir(resultado: bytes) -> Image.Image:
    return Image.open(io.BytesIO(resultado))


# --- faixa de tamanho e dimensões ---


@pytest.fixture(scope="module")
def foto_grande_com_muito_detalhe() -> FotoProcessada:
    # ruído é o pior caso para o WebP; processar leva alguns segundos, então roda uma vez só
    entrada = _bytes_da_imagem(_ruido(2000, 1500), "JPEG", quality=60)
    return processar_foto(entrada)


def test_foto_grande_com_muito_detalhe_fica_entre_50_e_80_kb(
    foto_grande_com_muito_detalhe: FotoProcessada,
):
    # assert
    assert 50 * KB <= len(foto_grande_com_muito_detalhe.dados) <= 80 * KB
    assert foto_grande_com_muito_detalhe.tamanho_bytes == len(foto_grande_com_muito_detalhe.dados)


def test_foto_grande_e_reduzida_mas_respeita_o_piso_de_dimensao(
    foto_grande_com_muito_detalhe: FotoProcessada,
):
    # act
    lado_maior = max(foto_grande_com_muito_detalhe.largura, foto_grande_com_muito_detalhe.altura)

    # assert
    assert fotos.LADO_MAIOR_MINIMO <= lado_maior < fotos.LADO_MAIOR_INICIAL


def test_resultado_declara_as_mesmas_dimensoes_da_imagem_gravada(
    foto_grande_com_muito_detalhe: FotoProcessada,
):
    # act
    imagem = _abrir(foto_grande_com_muito_detalhe.dados)

    # assert
    assert imagem.size == (
        foto_grande_com_muito_detalhe.largura,
        foto_grande_com_muito_detalhe.altura,
    )


def test_foto_grande_e_simples_cabe_no_primeiro_passo_com_lado_maior_de_1280():
    # arrange
    entrada = _bytes_da_imagem(_gradiente(4000, 3000), "PNG")

    # act
    resultado = processar_foto(entrada)

    # assert
    assert (resultado.largura, resultado.altura) == (1280, 960)
    assert len(resultado.dados) < 50 * KB


def test_foto_pequena_nao_e_ampliada_nem_piorada():
    # arrange
    imagem = _gradiente(400, 300)
    entrada = _bytes_da_imagem(imagem, "PNG")

    # act
    resultado = processar_foto(entrada)

    # assert: mesmas dimensões e qualidade inicial (80), a mesma que codificar direto
    assert (resultado.largura, resultado.altura) == (400, 300)
    assert len(resultado.dados) == len(_bytes_da_imagem(imagem, "WEBP", quality=80))


def test_se_nem_no_piso_couber_guarda_o_menor_resultado(monkeypatch: pytest.MonkeyPatch):
    # arrange: teto impossível de cumprir força o algoritmo a esgotar todas as tentativas
    monkeypatch.setattr(fotos, "TAMANHO_MAXIMO_SAIDA", 100)
    entrada = _bytes_da_imagem(_ruido(600, 500), "PNG")

    # act
    resultado = processar_foto(entrada)

    # assert: parou no piso de dimensão e com a qualidade mínima
    assert max(resultado.largura, resultado.altura) == fotos.LADO_MAIOR_MINIMO
    no_piso = _ruido(600, 500)
    no_piso.thumbnail((fotos.LADO_MAIOR_MINIMO, fotos.LADO_MAIOR_MINIMO))
    menor_possivel = _bytes_da_imagem(no_piso, "WEBP", quality=fotos.QUALIDADE_MINIMA)
    assert len(resultado.dados) <= len(menor_possivel) * 1.1


# --- formato de saída, orientação e metadados ---


def test_saida_e_webp_em_rgb():
    # arrange
    entrada = _bytes_da_imagem(_gradiente(300, 200), "PNG")

    # act
    imagem = _abrir(processar_foto(entrada).dados)

    # assert
    assert imagem.format == "WEBP"
    assert imagem.mode == "RGB"


@pytest.mark.parametrize("formato", ["JPEG", "PNG", "WEBP"])
def test_aceita_jpeg_png_e_webp(formato: str):
    # arrange
    entrada = _bytes_da_imagem(_gradiente(300, 200), formato)

    # act
    resultado = processar_foto(entrada)

    # assert
    assert (resultado.largura, resultado.altura) == (300, 200)


def test_retrato_com_exif_de_rotacao_sai_em_pe():
    # arrange: pixels 300x200 com orientação 6 (girar 90° para exibir), ou seja, retrato 200x300
    exif = Image.Exif()
    exif[0x0112] = 6
    entrada = _bytes_da_imagem(_gradiente(300, 200), "JPEG", exif=exif)

    # act
    resultado = processar_foto(entrada)

    # assert
    assert (resultado.largura, resultado.altura) == (200, 300)


def test_exif_com_localizacao_e_removido_dos_bytes_e_da_leitura():
    # arrange: EXIF com GPS, que é o motivo de remover metadados (AGENTS.md §2.8)
    exif = Image.Exif()
    exif[0x010F] = "FabricanteSecreto"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (23.0, 33.0, 1.0)
    gps[3] = "W"
    gps[4] = (46.0, 38.0, 1.0)
    entrada = _bytes_da_imagem(_gradiente(300, 200), "JPEG", exif=exif)
    assert b"FabricanteSecreto" in entrada  # a entrada realmente traz o metadado

    # act
    resultado = processar_foto(entrada)

    # assert
    assert len(_abrir(resultado.dados).getexif()) == 0
    assert b"EXIF" not in resultado.dados
    assert b"FabricanteSecreto" not in resultado.dados


def test_perfil_de_cor_e_texto_do_png_nao_sobrevivem():
    # arrange
    perfil = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    imagem = _gradiente(300, 200)
    imagem.info["Comment"] = "SegredoNoPNG"
    entrada = _bytes_da_imagem(imagem, "PNG", icc_profile=perfil)

    # act
    resultado = processar_foto(entrada)

    # assert
    for chave in ("icc_profile", "exif", "xmp"):
        assert chave not in _abrir(resultado.dados).info
    assert b"ICCP" not in resultado.dados
    assert b"SegredoNoPNG" not in resultado.dados


def test_png_com_transparencia_vira_fundo_branco_e_nao_preto():
    # arrange: RGBA todo transparente (com RGB preto por baixo)
    imagem = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    entrada = _bytes_da_imagem(imagem, "PNG")

    # act
    saida = _abrir(processar_foto(entrada).dados)

    # assert
    assert all(canal >= 240 for canal in saida.getpixel((100, 50)))


def test_png_de_paleta_com_transparencia_tambem_vira_fundo_branco():
    # arrange
    imagem = Image.new("P", (200, 100), 0)
    imagem.putpalette([0, 0, 0] * 256)
    entrada = _bytes_da_imagem(imagem, "PNG", transparency=0)

    # act
    saida = _abrir(processar_foto(entrada).dados)

    # assert
    assert all(canal >= 240 for canal in saida.getpixel((100, 50)))


def test_jpeg_em_tons_de_cinza_e_aceito():
    # arrange
    entrada = _bytes_da_imagem(Image.new("L", (200, 100), 128), "JPEG")

    # act
    imagem = _abrir(processar_foto(entrada).dados)

    # assert
    assert imagem.mode == "RGB"


# --- rejeições ---


def test_texto_qualquer_nao_e_imagem():
    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(b"isto nao e uma imagem")

    # assert
    assert "JPEG, PNG ou WebP" in str(excecao.value)


def test_formato_nao_suportado_e_recusado_pelo_conteudo_e_nao_pela_extensao():
    # arrange: um GIF de verdade
    entrada = _bytes_da_imagem(Image.new("P", (10, 10)), "GIF")

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(entrada)

    # assert
    assert "JPEG, PNG ou WebP" in str(excecao.value)


@pytest.mark.parametrize("marca", [b"heic", b"heix", b"mif1"])
def test_heic_e_recusado_com_mensagem_propria(marca: bytes):
    # arrange: cabeçalho de arquivo HEIC (caixa `ftyp`)
    entrada = b"\x00\x00\x00\x18ftyp" + marca + b"\x00" * 32

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(entrada)

    # assert
    assert "HEIC" in str(excecao.value)


def test_arquivo_vazio_e_recusado():
    # act / assert
    with pytest.raises(FotoInvalida):
        processar_foto(b"")


def test_jpeg_truncado_e_recusado_como_corrompido():
    # arrange
    completo = _bytes_da_imagem(_ruido(400, 300), "JPEG")

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(completo[: len(completo) // 2])

    # assert
    assert "corrompida" in str(excecao.value)


def test_cabecalho_de_jpeg_seguido_de_lixo_e_recusado():
    # arrange
    gerador = random.Random(2)
    entrada = b"\xff\xd8\xff\xe0" + gerador.randbytes(2000)

    # act / assert
    with pytest.raises(FotoInvalida):
        processar_foto(entrada)


def test_arquivo_acima_de_20_mb_e_recusado_antes_de_decodificar():
    # arrange
    entrada = b"\x00" * (fotos.TAMANHO_MAXIMO_ENTRADA + 1)

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(entrada)

    # assert
    assert "20 MB" in str(excecao.value)


def test_imagem_com_pixels_demais_e_recusada(monkeypatch: pytest.MonkeyPatch):
    # arrange
    monkeypatch.setattr(fotos, "LIMITE_DE_PIXELS", 1000)
    entrada = _bytes_da_imagem(Image.new("RGB", (100, 100)), "PNG")

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(entrada)

    # assert
    assert "pixels" in str(excecao.value)


def test_bomba_de_descompressao_e_recusada():
    # arrange: PNG de 1 bit com ~196 milhões de pixels; pequeno em disco, enorme na memória
    entrada = _bytes_da_imagem(Image.new("1", (14000, 14000)), "PNG")
    assert len(entrada) < fotos.TAMANHO_MAXIMO_ENTRADA

    # act
    with pytest.raises(FotoInvalida) as excecao:
        processar_foto(entrada)

    # assert
    assert "pixels" in str(excecao.value)


def test_foto_invalida_e_um_erro_de_dominio():
    # assert
    assert issubclass(FotoInvalida, ErroDeDominio)
