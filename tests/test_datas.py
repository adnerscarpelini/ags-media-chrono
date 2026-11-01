"""Leitura de datas. Os dicionários de tags imitam a saída real do ExifTool (-json -G1) para
cada tipo de origem (iPhone, WhatsApp, Nikon), com valores alterados."""

import subprocess
from datetime import UTC, datetime, timedelta, timezone

import pytest
from PIL import Image

from ags_media_chrono.core.datas import (
    Origem,
    _fuso_camera,
    candidatas_de_tags,
    formatar_fuso,
    interpretar_data,
    interpretar_fuso,
    ler_datas,
)
from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar

BRT = timezone(timedelta(hours=-3))


def _tem(nome):
    try:
        localizar(nome)
        return True
    except FerramentaNaoEncontrada:
        return False


requer_exiftool = pytest.mark.skipif(not _tem("exiftool"), reason="ExifTool não instalado")

IPHONE_HEIC = {
    "System:FileModifyDate": "2026:10:29 09:26:20-03:00",
    "System:FileAccessDate": "2026:11:01 12:10:16-03:00",
    "System:FileCreateDate": "2026:11:01 10:46:00-03:00",
    "IFD0:ModifyDate": "2026:10:28 10:00:08",
    "ExifIFD:DateTimeOriginal": "2026:10:28 10:00:08",
    "ExifIFD:CreateDate": "2026:10:28 10:00:08",
    "ExifIFD:OffsetTime": "-03:00",
    "ExifIFD:OffsetTimeOriginal": "-03:00",
    "ExifIFD:OffsetTimeDigitized": "-03:00",
    "ExifIFD:SubSecTimeOriginal": "790",
    "GPS:GPSTimeStamp": "13:00:05",
    "GPS:GPSDateStamp": "2026:10:28",
    "XMP-xmp:CreateDate": "2026:10:28 10:00:08",
    "XMP-photoshop:DateCreated": "2026:10:28 10:00:08",
    "ICC-header:ProfileDateTime": "2022:01:01 00:00:00",
    "Composite:SubSecDateTimeOriginal": "2026:10:28 10:00:08.790-03:00",
    "Composite:GPSDateTime": "2026:10:28 13:00:05Z",
}

IPHONE_MOV = {
    "System:FileModifyDate": "2026:10:22 07:25:28-03:00",
    "QuickTime:CreateDate": "2026:10:21 21:53:40",
    "QuickTime:ModifyDate": "2026:10:21 21:54:55",
    **{f"Track{i}:TrackCreateDate": "2026:10:21 21:53:40" for i in range(1, 8)},
    **{f"Track{i}:MediaCreateDate": "2026:10:21 21:53:40" for i in range(1, 8)},
    "Keys:CreationDate": "2026:10:21 18:53:40-03:00",
}

WHATSAPP_MP4 = {
    "System:FileModifyDate": "2026:10:30 08:02:48-03:00",
    "System:FileCreateDate": "2026:11:01 10:45:52-03:00",
    "QuickTime:CreateDate": "0000:00:00 00:00:00",
    "QuickTime:ModifyDate": "0000:00:00 00:00:00",
    "Track1:TrackCreateDate": "0000:00:00 00:00:00",
}

NIKON_NEF = {
    "IFD0:ModifyDate": "2017:06:17 14:44:06",
    "ExifIFD:DateTimeOriginal": "2017:06:17 14:44:06",
    "ExifIFD:CreateDate": "2017:06:17 14:44:06",
    "IFD0:DateTimeOriginal": "2017:06:17 14:44:06",
    "XMP-xmp:CreateDate": "2017:06:17 14:44:06.76",
    "Nikon:TimeZone": "+01:00",
    "Nikon:DaylightSavings": "Yes",
    "Nikon:DateDisplayFormat": "Y/M/D",
    "Nikon:PowerUpTime": "0000:00:00 00:00:00",
}


def _por_campo(tags):
    return {c.campo: c for c in candidatas_de_tags(tags)}


# --- interpretação ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2023:05:12 14:30:00", (datetime(2023, 5, 12, 14, 30), False)),
        ("2023:05:12 14:30:00.79-03:00", (datetime(2023, 5, 12, 14, 30, tzinfo=BRT), False)),
        ("2023:05:12 17:30:00Z", (datetime(2023, 5, 12, 17, 30, tzinfo=UTC), False)),
        ("2023:05:12 14:30", (datetime(2023, 5, 12, 14, 30), False)),
        ("2023:05:12", (datetime(2023, 5, 12), True)),
        ("0000:00:00 00:00:00", None),
        ("1904:01:01 00:00:00", None),  # "zero" do QuickTime
        ("1970:01:01 00:00:00", None),  # "zero" do Unix
        ("2023:13:01 00:00:00", None),
        ("+01:00", None),
        ("Y/M/D", None),
        ("13:00:05", None),
        ("", None),
    ],
)
def test_interpretar_data(texto, esperado):
    assert interpretar_data(texto) == esperado


def test_fusos():
    assert interpretar_fuso("-03:00") == timedelta(hours=-3)
    assert interpretar_fuso("+0530") == timedelta(hours=5, minutes=30)
    assert interpretar_fuso("Z") == timedelta(0)
    assert interpretar_fuso("abc") is None
    assert formatar_fuso(timedelta(hours=-3)) == "-03:00"
    assert formatar_fuso(timedelta(hours=5, minutes=30)) == "+05:30"
    assert formatar_fuso(timedelta(0)) == "+00:00"


# --- origens ------------------------------------------------------------------------------


def test_iphone_heic():
    c = _por_campo(IPHONE_HEIC)
    assert set(c) == {
        "System:FileModifyDate", "System:FileCreateDate", "IFD0:ModifyDate",
        "ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate", "XMP-xmp:CreateDate",
        "XMP-photoshop:DateCreated", "Composite:GPSDateTime",
    }  # fmt: skip
    # Fuso EXIF (OffsetTimeOriginal) aplicado à data de captura
    assert c["ExifIFD:DateTimeOriginal"].valor == datetime(2026, 10, 28, 10, 0, 8, tzinfo=BRT)
    assert c["Composite:GPSDateTime"].origem == Origem.GPS
    assert c["Composite:GPSDateTime"].fuso == timedelta(0)
    assert c["XMP-xmp:CreateDate"].origem == Origem.XMP
    assert c["System:FileCreateDate"].origem == Origem.ARQUIVO
    assert _fuso_camera(IPHONE_HEIC) == timedelta(hours=-3)


def test_iphone_mov_agrupa_faixas_e_marca_utc():
    lista = candidatas_de_tags(IPHONE_MOV)
    c = {x.campo: x for x in lista}
    assert sum(1 for x in lista if x.campo == "Track:TrackCreateDate") == 1
    assert c["QuickTime:CreateDate"].utc_presumido
    assert not c["Keys:CreationDate"].utc_presumido
    assert c["Keys:CreationDate"].fuso == timedelta(hours=-3)
    # Mesmo instante, gravado de dois jeitos: UTC sem fuso e local com fuso
    utc = c["QuickTime:CreateDate"].valor.replace(tzinfo=UTC)
    assert utc == c["Keys:CreationDate"].valor


def test_whatsapp_sem_datas_internas():
    lista = candidatas_de_tags(WHATSAPP_MP4)
    assert {c.origem for c in lista} == {Origem.ARQUIVO}
    assert not any(c.captura for c in lista)


def test_nikon_fuso_com_horario_de_verao_e_campos_ignorados():
    c = _por_campo(NIKON_NEF)
    assert "Nikon:PowerUpTime" not in c
    assert c["IFD0:DateTimeOriginal"].captura
    assert _fuso_camera(NIKON_NEF) == timedelta(hours=2)
    assert _fuso_camera({**NIKON_NEF, "Nikon:DaylightSavings": "No"}) == timedelta(hours=1)
    assert _fuso_camera({"Nikon:TimeZone": "+00:00"}) == timedelta(0)


def test_campo_desconhecido_entra_como_nao_captura():
    [c] = candidatas_de_tags({"Samsung:SomeDate": "2020:01:02 03:04:05"})
    assert c.origem == Origem.FABRICANTE
    assert not c.captura and c.rotulo == "SomeDate"


@pytest.mark.parametrize(
    ("tags", "campo"),
    [
        (IPHONE_HEIC, "ExifIFD:DateTimeOriginal"),
        (IPHONE_MOV, "Keys:CreationDate"),
        (NIKON_NEF, "ExifIFD:DateTimeOriginal"),
        ({"QuickTime:CreateDate": "2020:01:01 10:00:00"}, "QuickTime:CreateDate"),
        (WHATSAPP_MP4, None),
    ],
)
def test_captura_sugerida(tags, campo):
    from ags_media_chrono.core.datas import DatasArquivo

    sugerida = DatasArquivo(None, candidatas_de_tags(tags)).captura_sugerida()
    assert (sugerida.campo if sugerida else None) == campo


# --- integração com o ExifTool ----------------------------------------------------------


@requer_exiftool
def test_ler_datas_jpeg_e_video(tmp_path):
    foto = tmp_path / "foto.jpg"
    Image.new("RGB", (8, 8)).save(foto)
    vazio = tmp_path / "vazio.jpg"
    vazio.touch()
    arquivos = [foto, vazio]

    with ExifTool() as et:
        assert et.gravar(
            foto,
            {
                "EXIF:DateTimeOriginal": "2023:05:12 14:30:00",
                "EXIF:OffsetTimeOriginal": "-03:00",
                "XMP-xmp:CreateDate": "2023:05:12 14:30:00",
            },
        ).ok
        if _tem("ffmpeg"):
            video = tmp_path / "video.mov"
            subprocess.run(
                [str(localizar("ffmpeg")), "-v", "error", "-f", "lavfi", "-i",
                 "testsrc=duration=1:size=64x64:rate=5", "-pix_fmt", "yuv420p", str(video)],
                check=True,
            )  # fmt: skip
            assert et.gravar(
                video,
                {
                    "QuickTime:CreateDate": "2023:05:12 17:30:00",
                    "Keys:CreationDate": "2023:05:12 14:30:00-03:00",
                },
            ).ok
            arquivos.append(video)
        resultados = ler_datas(arquivos, et)

    r_foto, r_vazio = resultados[:2]
    assert r_foto.captura_sugerida().valor == datetime(2023, 5, 12, 14, 30, tzinfo=BRT)
    assert r_foto.fuso_camera == timedelta(hours=-3)
    assert r_vazio.erro == "File is empty"
    if len(resultados) == 3:
        r_video = resultados[2]
        assert r_video.captura_sugerida().campo == "Keys:CreationDate"
        quicktime = next(c for c in r_video.candidatas if c.campo == "QuickTime:CreateDate")
        assert quicktime.utc_presumido
