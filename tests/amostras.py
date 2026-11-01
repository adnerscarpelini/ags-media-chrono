"""Amostras pequenas geradas na hora, imitando cada origem real (issue #23).

Nada de binários no repositório: Pillow/pillow-heif criam as fotos, o FFmpeg cria os vídeos e o
ExifTool grava os metadados típicos de cada origem.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pillow_heif
from PIL import Image

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar

pillow_heif.register_heif_opener()  # permite salvar .HEIC com o Pillow


def tem(nome: str) -> bool:
    try:
        localizar(nome)
        return True
    except FerramentaNaoEncontrada:
        return False


def _video(destino: Path) -> None:
    subprocess.run(
        [str(localizar("ffmpeg")), "-v", "error", "-y", "-f", "lavfi", "-i",
         "testsrc=duration=1:size=64x64:rate=5", "-pix_fmt", "yuv420p", str(destino)],
        check=True,
    )  # fmt: skip


def criar_amostras(pasta: Path, et: ExifTool) -> dict[str, Path]:
    """Cria as amostras e devolve {apelido: caminho}."""
    pasta.mkdir(parents=True, exist_ok=True)
    a: dict[str, Path] = {}

    # iPhone: HEIC e JPG com DateTimeOriginal + fuso, GPS em UTC
    a["iphone_heic"] = pasta / "IMG_0001.HEIC"
    Image.new("RGB", (64, 48), "green").save(a["iphone_heic"], format="HEIF")
    a["iphone_jpg"] = pasta / "IMG_0002.JPG"
    Image.new("RGB", (64, 48), "blue").save(a["iphone_jpg"])
    for chave in ("iphone_heic", "iphone_jpg"):
        r = et.gravar(a[chave], {
            "EXIF:Make": "Apple", "EXIF:Model": "iPhone 14",
            "EXIF:DateTimeOriginal": "2026:10:28 10:00:08",
            "EXIF:CreateDate": "2026:10:28 10:00:08",
            "EXIF:ModifyDate": "2026:10:28 10:00:08", "EXIF:OffsetTimeOriginal": "-03:00",
            "EXIF:OffsetTime": "-03:00", "GPS:GPSDateStamp": "2026:10:28",
            "GPS:GPSTimeStamp": "13:00:05",
        })  # fmt: skip
        assert r.ok, r.erros

    # WhatsApp: JPG e MP4 sem metadados de data (só o nome)
    a["whatsapp_jpg"] = pasta / "IMG-20230512-WA0001.jpg"
    Image.new("RGB", (64, 48), "yellow").save(a["whatsapp_jpg"])
    # Nikon: JPG com data sem fuso (fuso só nas notas do fabricante, que não simulamos)
    a["nikon_jpg"] = pasta / "DSC_0105.JPG"
    Image.new("RGB", (64, 48), "gray").save(a["nikon_jpg"])
    assert et.gravar(a["nikon_jpg"], {
        "EXIF:Make": "NIKON CORPORATION", "EXIF:Model": "NIKON D3400",
        "EXIF:DateTimeOriginal": "2017:06:17 14:44:06", "EXIF:CreateDate": "2017:06:17 14:44:06",
    }).ok  # fmt: skip
    # PNG (captura de tela) e BMP (formato sem metadados)
    a["screenshot_png"] = pasta / "Screenshot_20230512-143000.png"
    Image.new("RGB", (64, 48), "white").save(a["screenshot_png"])
    a["bmp"] = pasta / "antiga.bmp"
    Image.new("RGB", (8, 8), "black").save(a["bmp"])

    if tem("ffmpeg"):
        # iPhone MOV: QuickTime em UTC + Keys:CreationDate local
        a["iphone_mov"] = pasta / "IMG_0003.MOV"
        _video(a["iphone_mov"])
        assert et.gravar(a["iphone_mov"], {
            "QuickTime:CreateDate": "2026:10:21 21:53:40",
            "QuickTime:TrackCreateDate": "2026:10:21 21:53:40",
            "QuickTime:MediaCreateDate": "2026:10:21 21:53:40",
            "Keys:CreationDate": "2026:10:21 18:53:40-03:00",
        }).ok  # fmt: skip
        # WhatsApp MP4: datas QuickTime zeradas
        a["whatsapp_mp4"] = pasta / "VID-20230512-WA0003.mp4"
        _video(a["whatsapp_mp4"])
        # AVI: formato sem gravação de metadados
        a["avi"] = pasta / "camera_antiga.avi"
        subprocess.run(
            [str(localizar("ffmpeg")), "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc=duration=1:size=64x64:rate=5", str(a["avi"])],
            check=True,
        )  # fmt: skip
    return a
