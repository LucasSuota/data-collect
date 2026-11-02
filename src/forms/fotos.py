"""Processa a foto enviada: valida, orienta, remove metadados e converte para WebP (§2.8).

Função pura de bytes para bytes: não lê nem grava arquivo (isso é do `servico.py`). O original
é descartado, só o WebP processado existe depois daqui.
"""

import io
from collections.abc import Iterator
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from forms.models import FotoInvalida

KB = 1024

TAMANHO_MAXIMO_ENTRADA = 20 * 1024 * KB
# Barra bomba de descompressão: um arquivo pequeno pode declarar bilhões de pixels.
# 50 MP deixa passar as câmeras de celular de 48 MP.
LIMITE_DE_PIXELS = 50_000_000

# O algoritmo persegue o teto de 80 KB; os 50 KB do §2.8 são só o alvo típico de uma foto
# grande, não um piso: foto simples que já cabe com qualidade 80 não é piorada nem ampliada.
TAMANHO_MAXIMO_SAIDA = 80 * KB
LADO_MAIOR_INICIAL = 1280
LADO_MAIOR_MINIMO = 480
FATOR_DE_REDUCAO = 0.85
QUALIDADE_INICIAL = 80
QUALIDADE_MINIMA = 40
PASSO_DE_QUALIDADE = 5

# Reconhecidos pelo conteúdo, nunca pela extensão do arquivo.
_FORMATOS_ACEITOS = ["JPEG", "PNG", "WEBP"]
# Marcas da caixa `ftyp` dos arquivos HEIC/HEIF (fotos do iPhone, por exemplo).
_MARCAS_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


@dataclass(frozen=True)
class FotoProcessada:
    dados: bytes
    largura: int
    altura: int

    @property
    def tamanho_bytes(self) -> int:
        return len(self.dados)


def processar_foto(dados: bytes) -> FotoProcessada:
    """Devolve o WebP processado, ou levanta `FotoInvalida` com o motivo em PT-BR."""
    if len(dados) > TAMANHO_MAXIMO_ENTRADA:
        raise FotoInvalida(
            f"A foto tem mais de {TAMANHO_MAXIMO_ENTRADA // (KB * KB)} MB. Envie uma menor."
        )

    imagem = _abrir_e_decodificar(dados)
    rgb = _para_rgb_sem_metadados(ImageOps.exif_transpose(imagem))
    return _comprimir(rgb)


def _abrir_e_decodificar(dados: bytes) -> Image.Image:
    try:
        imagem = Image.open(io.BytesIO(dados), formats=_FORMATOS_ACEITOS)
        # `open` só lê o cabeçalho: o tamanho é conferido antes de decodificar os pixels.
        if imagem.width * imagem.height > LIMITE_DE_PIXELS:
            raise _pixels_demais()
        imagem.load()
    except UnidentifiedImageError as erro:
        raise FotoInvalida(_motivo_do_formato_recusado(dados)) from erro
    except Image.DecompressionBombError as erro:
        raise _pixels_demais() from erro
    except (OSError, ValueError, SyntaxError) as erro:
        # Truncado ou com dados quebrados: o Pillow levanta tipos variados conforme o formato.
        raise FotoInvalida("A imagem está corrompida ou incompleta.") from erro
    return imagem


def _pixels_demais() -> FotoInvalida:
    return FotoInvalida(
        f"A imagem tem pixels demais (máximo {LIMITE_DE_PIXELS // 1_000_000} megapixels)."
    )


def _motivo_do_formato_recusado(dados: bytes) -> str:
    if dados[4:8] == b"ftyp" and dados[8:12] in _MARCAS_HEIC:
        return (
            "Fotos em formato HEIC não são suportadas. Converta para JPEG ou PNG "
            "(no iPhone: Ajustes > Câmera > Formatos > Mais Compatível)."
        )
    return "Formato de imagem não suportado. Envie JPEG, PNG ou WebP."


def _para_rgb_sem_metadados(imagem: Image.Image) -> Image.Image:
    if imagem.has_transparency_data:
        # `convert("RGB")` descartaria o canal alfa e o pixel transparente ficaria preto.
        rgba = imagem.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base

    # Copiar os pixels para uma imagem nova deixa para trás tudo o que estava em `info`
    # (EXIF, XMP, perfil ICC, textos do PNG). O EXIF traz a localização exata da foto.
    rgb = imagem.convert("RGB")
    limpa = Image.new("RGB", rgb.size)
    limpa.paste(rgb)
    return limpa


def _comprimir(imagem: Image.Image) -> FotoProcessada:
    tentativas = _tentativas(imagem)
    menor = next(tentativas)
    if menor.tamanho_bytes <= TAMANHO_MAXIMO_SAIDA:
        return menor

    for tentativa in tentativas:
        if tentativa.tamanho_bytes <= TAMANHO_MAXIMO_SAIDA:
            return tentativa
        if tentativa.tamanho_bytes < menor.tamanho_bytes:
            menor = tentativa
    # Nem no piso de dimensão e qualidade coube: guarda o menor resultado obtido.
    return menor


def _tentativas(imagem: Image.Image) -> Iterator[FotoProcessada]:
    """Gera os candidatos na ordem do §2.8: qualidade desce a cada passo, depois o tamanho."""
    lado = min(LADO_MAIOR_INICIAL, max(imagem.size))  # nunca amplia
    while True:
        redimensionada = _redimensionar(imagem, lado)
        for qualidade in range(QUALIDADE_INICIAL, QUALIDADE_MINIMA - 1, -PASSO_DE_QUALIDADE):
            yield _codificar(redimensionada, qualidade)
        if lado <= LADO_MAIOR_MINIMO:
            return
        lado = max(LADO_MAIOR_MINIMO, int(lado * FATOR_DE_REDUCAO))


def _redimensionar(imagem: Image.Image, lado_maior: int) -> Image.Image:
    escala = lado_maior / max(imagem.size)
    if escala >= 1:
        return imagem
    tamanho = (max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala)))
    return imagem.resize(tamanho, Image.Resampling.LANCZOS)


def _codificar(imagem: Image.Image, qualidade: int) -> FotoProcessada:
    destino = io.BytesIO()
    imagem.save(destino, "WEBP", quality=qualidade)
    return FotoProcessada(destino.getvalue(), imagem.width, imagem.height)
