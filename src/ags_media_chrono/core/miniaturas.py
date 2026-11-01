"""Geração de miniaturas (fotos, HEIC, RAW e vídeos) e cache em disco.

- Fotos comuns: Pillow, respeitando a orientação EXIF.
- HEIC/HEIF: pillow-heif (a orientação já vem aplicada pelo libheif).
- RAW (NEF etc.): JPEG de prévia embutido, extraído pelo ExifTool.
- Vídeos: um quadro extraído pelo FFmpeg (que já aplica a rotação do vídeo) e a duração
  lida do cabeçalho que o próprio FFmpeg imprime.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import localizar
from ags_media_chrono.core.midias import Midia, TipoMidia

pillow_heif.register_heif_opener()

TAMANHO_MINIATURA = 320  # lado maior, em pixels
QUALIDADE_JPEG = 85
VERSAO_CACHE = 1  # incremente se o formato das miniaturas mudar

EXTENSOES_RAW = frozenset({".nef", ".nrw", ".dng", ".cr2", ".cr3", ".arw", ".raf", ".orf", ".rw2"})
# Ordem de preferência: prévias menores primeiro (mais rápidas), miniatura EXIF por último.
TAGS_PREVIA_RAW = ("PreviewImage", "JpgFromRaw", "OtherImage", "ThumbnailImage")
# Na visualização ampliada, a prévia em resolução total vem primeiro.
TAGS_AMPLIADA_RAW = ("JpgFromRaw", "OtherImage", "PreviewImage", "ThumbnailImage")

# Orientação EXIF (1–8) -> transformações do Pillow
_TRANSPOSICOES = {
    2: [Image.Transpose.FLIP_LEFT_RIGHT],
    3: [Image.Transpose.ROTATE_180],
    4: [Image.Transpose.FLIP_TOP_BOTTOM],
    5: [Image.Transpose.TRANSPOSE],
    6: [Image.Transpose.ROTATE_270],
    7: [Image.Transpose.TRANSVERSE],
    8: [Image.Transpose.ROTATE_90],
}

_SEM_JANELA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class ErroMiniatura(Exception):
    pass


@dataclass(frozen=True)
class Miniatura:
    jpeg: bytes
    duracao: float | None = None  # só para vídeos


# --- cache ------------------------------------------------------------------------------


def pasta_cache_padrao() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "ags-media-chrono" / "miniaturas"


class CacheMiniaturas:
    """Arquivos <hash>.jpg (+ <hash>.json com a duração dos vídeos), em subpastas de 2 letras.

    A chave inclui caminho, tamanho e data de modificação: se o arquivo mudar, a miniatura é
    gerada de novo.
    """

    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or pasta_cache_padrao()

    def chave(self, midia: Midia) -> str:
        texto = (
            f"{VERSAO_CACHE}|{TAMANHO_MINIATURA}|{os.path.normcase(midia.caminho.absolute())}|"
            f"{midia.tamanho}|{midia.modificado:.6f}"
        )
        return hashlib.sha1(texto.encode("utf-8")).hexdigest()

    def _caminhos(self, midia: Midia) -> tuple[Path, Path]:
        chave = self.chave(midia)
        base = self.pasta / chave[:2] / chave
        return base.with_suffix(".jpg"), base.with_suffix(".json")

    def obter(self, midia: Midia) -> Miniatura | None:
        jpg, meta = self._caminhos(midia)
        try:
            dados = jpg.read_bytes()
        except OSError:
            return None
        duracao = None
        if midia.tipo == TipoMidia.VIDEO:
            try:
                duracao = json.loads(meta.read_text(encoding="utf-8")).get("duracao")
            except (OSError, ValueError):
                pass
        return Miniatura(dados, duracao)

    def salvar(self, midia: Midia, miniatura: Miniatura) -> None:
        jpg, meta = self._caminhos(midia)
        jpg.parent.mkdir(parents=True, exist_ok=True)
        if miniatura.duracao is not None:
            _gravar_atomico(meta, json.dumps({"duracao": miniatura.duracao}).encode("utf-8"))
        _gravar_atomico(jpg, miniatura.jpeg)


def _gravar_atomico(destino: Path, dados: bytes) -> None:
    temporario = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    temporario.write_bytes(dados)
    os.replace(temporario, destino)


# --- geração -------------------------------------------------------------------------------


def para_rgb(imagem: Image.Image) -> Image.Image:
    """Converte para RGB; transparência vira fundo cinza escuro (combina com o tema)."""
    if imagem.mode in ("RGBA", "LA", "P"):
        imagem = imagem.convert("RGBA")
        fundo = Image.new("RGB", imagem.size, (42, 42, 42))
        fundo.paste(imagem, mask=imagem.getchannel("A"))
        return fundo
    return imagem if imagem.mode == "RGB" else imagem.convert("RGB")


def _para_jpeg(imagem: Image.Image) -> bytes:
    imagem.thumbnail((TAMANHO_MINIATURA, TAMANHO_MINIATURA), Image.Resampling.LANCZOS)
    imagem = para_rgb(imagem)
    saida = io.BytesIO()
    imagem.save(saida, "JPEG", quality=QUALIDADE_JPEG, optimize=True)
    return saida.getvalue()


def _foto(caminho: Path, lado: int = TAMANHO_MINIATURA * 2) -> Image.Image:
    imagem = Image.open(caminho)
    # Para JPEG grandes, decodifica direto em resolução reduzida (bem mais rápido).
    imagem.draft("RGB", (lado, lado))
    return ImageOps.exif_transpose(imagem)


def _raw(
    caminho: Path,
    exiftool: ExifTool,
    lado: int = TAMANHO_MINIATURA * 2,
    tags: tuple[str, ...] = TAGS_PREVIA_RAW,
) -> Image.Image:
    for tag in tags:
        dados = exiftool.extrair_binario(caminho, tag)
        if dados:
            break
    else:
        raise ErroMiniatura("Nenhuma prévia JPEG embutida no arquivo RAW")

    imagem = Image.open(io.BytesIO(dados))
    imagem.draft("RGB", (lado, lado))
    imagem.load()
    # A prévia não carrega a orientação; ela fica no próprio RAW.
    orientacao = exiftool.executar("-n", "-s3", "-Orientation", str(caminho.absolute())).stdout
    for t in _TRANSPOSICOES.get(int(orientacao.strip() or 1), []):
        imagem = imagem.transpose(t)
    return imagem


_DURACAO = re.compile(rb"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


def duracao_video(caminho: Path, ffmpeg: Path | None = None) -> float | None:
    """Duração em segundos, lida do cabeçalho que o FFmpeg imprime ao abrir o arquivo.

    (Dispensa o ffprobe, que tem o mesmo tamanho do ffmpeg — ~130 MB a menos no pacote.)
    """
    resultado = subprocess.run(
        [str(ffmpeg or localizar("ffmpeg")), "-hide_banner", "-i", str(caminho)],
        capture_output=True,
        timeout=30,
        creationflags=_SEM_JANELA,
    )  # sem arquivo de saída o ffmpeg termina com erro, mas o cabeçalho já foi impresso
    m = _DURACAO.search(resultado.stderr)
    if not m:
        return None
    horas, minutos, segundos = m.groups()
    return int(horas) * 3600 + int(minutos) * 60 + float(segundos)


def _quadro_video(caminho: Path, segundo: float, ffmpeg: Path) -> bytes:
    escala = f"scale={TAMANHO_MINIATURA}:{TAMANHO_MINIATURA}:force_original_aspect_ratio=decrease"
    resultado = subprocess.run(
        [
            str(ffmpeg),
            "-v", "error",
            "-ss", f"{segundo:.3f}",
            "-i", str(caminho),
            "-frames:v", "1",
            "-vf", escala,
            "-f", "image2pipe",
            "-c:v", "png",
            "-",
        ],
        capture_output=True,
        timeout=60,
        creationflags=_SEM_JANELA,
    )  # fmt: skip
    return resultado.stdout


def _video(caminho: Path) -> tuple[Image.Image, float | None]:
    duracao = duracao_video(caminho)
    ffmpeg = localizar("ffmpeg")
    # Um pouco depois do início evita quadros pretos de abertura.
    segundo = min(1.0, duracao * 0.1) if duracao else 0.0
    dados = _quadro_video(caminho, segundo, ffmpeg)
    if not dados and segundo:
        dados = _quadro_video(caminho, 0.0, ffmpeg)
    if not dados:
        raise ErroMiniatura("FFmpeg não conseguiu extrair um quadro do vídeo")
    return Image.open(io.BytesIO(dados)), duracao


def gerar_miniatura(midia: Midia, exiftool: ExifTool | None = None) -> Miniatura:
    """Gera a miniatura (JPEG) de uma mídia. Pode levantar ErroMiniatura ou erros do Pillow."""
    caminho = midia.caminho
    if midia.tipo == TipoMidia.VIDEO:
        imagem, duracao = _video(caminho)
        return Miniatura(_para_jpeg(imagem), duracao)
    if caminho.suffix.lower() in EXTENSOES_RAW:
        if exiftool is None:
            raise ErroMiniatura("ExifTool necessário para miniaturas de arquivos RAW")
        return Miniatura(_para_jpeg(_raw(caminho, exiftool)))
    return Miniatura(_para_jpeg(_foto(caminho)))


def imagem_ampliada(midia: Midia, lado_max: int, exiftool: ExifTool | None = None) -> Image.Image:
    """Imagem em RGB com o lado maior até `lado_max`, para a visualização ampliada (fotos)."""
    caminho = midia.caminho
    if caminho.suffix.lower() in EXTENSOES_RAW:
        if exiftool is None:
            raise ErroMiniatura("ExifTool necessário para abrir arquivos RAW")
        imagem = _raw(caminho, exiftool, lado_max, TAGS_AMPLIADA_RAW)
    else:
        imagem = _foto(caminho, lado_max)
    imagem.thumbnail((lado_max, lado_max), Image.Resampling.LANCZOS)
    return para_rgb(imagem)
