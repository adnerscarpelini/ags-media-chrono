import io
import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar
from ags_media_chrono.core.midias import Midia, TipoMidia, tipo_por_extensao
from ags_media_chrono.core.miniaturas import (
    TAMANHO_MINIATURA,
    CacheMiniaturas,
    ErroMiniatura,
    Miniatura,
    gerar_miniatura,
    pasta_cache_padrao,
)


def _tem(nome):
    try:
        localizar(nome)
        return True
    except FerramentaNaoEncontrada:
        return False


requer_exiftool = pytest.mark.skipif(not _tem("exiftool"), reason="ExifTool não instalado")
requer_ffmpeg = pytest.mark.skipif(not _tem("ffmpeg"), reason="FFmpeg não instalado")


def _midia(caminho: Path) -> Midia:
    st = caminho.stat()
    return Midia(caminho, tipo_por_extensao(caminho.name), st.st_size, st.st_mtime)


def _tamanho(mini: Miniatura) -> tuple[int, int]:
    return Image.open(io.BytesIO(mini.jpeg)).size


def test_jpeg_reduzido_mantendo_proporcao(tmp_path):
    foto = tmp_path / "grande.jpg"
    Image.new("RGB", (4000, 3000), "orange").save(foto)
    assert _tamanho(gerar_miniatura(_midia(foto))) == (TAMANHO_MINIATURA, 240)


def test_jpeg_respeita_orientacao_exif(tmp_path):
    foto = tmp_path / "girada.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: girar 90° no sentido horário
    Image.new("RGB", (400, 300), "blue").save(foto, exif=exif)
    largura, altura = _tamanho(gerar_miniatura(_midia(foto)))
    assert altura > largura


def test_png_com_transparencia(tmp_path):
    foto = tmp_path / "transparente.png"
    Image.new("RGBA", (100, 50), (255, 0, 0, 0)).save(foto)
    assert _tamanho(gerar_miniatura(_midia(foto))) == (100, 50)  # não amplia


def test_heic(tmp_path):
    foto = tmp_path / "IMG_0001.HEIC"
    Image.new("RGB", (800, 600), "green").save(foto, format="HEIF")
    assert _tamanho(gerar_miniatura(_midia(foto))) == (TAMANHO_MINIATURA, 240)


def test_arquivo_corrompido_gera_erro(tmp_path):
    foto = tmp_path / "ruim.jpg"
    foto.write_bytes(b"nao e imagem")
    with pytest.raises(Exception):  # noqa: B017 — Pillow levanta tipos variados
        gerar_miniatura(_midia(foto))


def test_raw_sem_exiftool_gera_erro(tmp_path):
    raw = tmp_path / "DSC_0001.NEF"
    raw.write_bytes(b"x")
    with pytest.raises(ErroMiniatura):
        gerar_miniatura(_midia(raw), exiftool=None)


@requer_exiftool
def test_raw_usa_previa_embutida_e_orientacao(tmp_path):
    # Não temos um NEF de exemplo no repositório: simulamos um RAW com um JPEG que contém
    # uma miniatura EXIF embutida (ThumbnailImage) e orientação 8 (girar 270°).
    previa = tmp_path / "previa.jpg"
    Image.new("RGB", (160, 120), "red").save(previa)
    base = tmp_path / "base.jpg"
    Image.new("RGB", (64, 48), "gray").save(base)
    with ExifTool() as et:
        r = et.gravar(base, {"ThumbnailImage<": str(previa), "EXIF:Orientation#": "8"})
        assert r.ok, r.erros
        raw = base.rename(tmp_path / "DSC_0001.NEF")
        mini = gerar_miniatura(_midia(raw), exiftool=et)
    largura, altura = _tamanho(mini)
    assert (largura, altura) == (120, 160)  # prévia 160x120 girada
    cor = Image.open(io.BytesIO(mini.jpeg)).getpixel((60, 80))
    assert cor[0] > 200 and cor[1] < 60  # é a prévia vermelha, não a imagem cinza


@requer_ffmpeg
def test_video_quadro_e_duracao(tmp_path):
    video = tmp_path / "VID-20230512-WA0001.mp4"
    subprocess.run(
        [str(localizar("ffmpeg")), "-v", "error", "-f", "lavfi", "-i",
         "testsrc=duration=3:size=640x360:rate=10", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )  # fmt: skip
    mini = gerar_miniatura(_midia(video))
    assert _tamanho(mini) == (TAMANHO_MINIATURA, 180)
    assert mini.duracao == pytest.approx(3.0, abs=0.2)


@requer_ffmpeg
def test_video_invalido_gera_erro(tmp_path):
    video = tmp_path / "quebrado.mov"
    video.write_bytes(b"nao e video")
    with pytest.raises(ErroMiniatura):
        gerar_miniatura(_midia(video))


# --- cache --------------------------------------------------------------------------------


def test_cache_salva_e_recupera(tmp_path):
    cache = CacheMiniaturas(tmp_path / "cache")
    arquivo = tmp_path / "v.mp4"
    arquivo.write_bytes(b"x")
    midia = _midia(arquivo)
    assert cache.obter(midia) is None
    cache.salvar(midia, Miniatura(b"jpeg", duracao=12.5))
    assert cache.obter(midia) == Miniatura(b"jpeg", 12.5)


def test_cache_invalida_quando_arquivo_muda(tmp_path):
    cache = CacheMiniaturas(tmp_path / "cache")
    arquivo = tmp_path / "a.jpg"
    arquivo.write_bytes(b"x")
    cache.salvar(_midia(arquivo), Miniatura(b"jpeg"))
    os.utime(arquivo, (1_700_000_000, 1_700_000_000))
    assert cache.obter(_midia(arquivo)) is None


def test_pasta_cache_padrao_por_sistema(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "win"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "linux"))
    pasta = pasta_cache_padrao()
    assert pasta.name == "miniaturas"
    assert pasta.parent.name == "ags-media-chrono"
    assert pasta.parent.parent in (tmp_path / "win", tmp_path / "linux")


def test_tipo_midia_video():
    assert tipo_por_extensao("a.MOV") == TipoMidia.VIDEO
