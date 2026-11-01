# -*- mode: python -*-
# Gera dist/ags-media-chrono/ (pasta única, sem console). Use: python tools/empacotar.py
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).parent
PACOTE = RAIZ / "src" / "ags_media_chrono"
WINDOWS = sys.platform == "win32"

# ExifTool e FFmpeg vão em <app>/_internal/tools/bin (procurados em sys._MEIPASS/tools/bin).
dados = [
    (str(PACOTE / "recursos"), "ags_media_chrono/recursos"),
    (str(RAIZ / "tools" / "bin" / "exiftool"), "tools/bin/exiftool"),
    (str(RAIZ / "tools" / "bin" / "ffmpeg" / ("ffmpeg.exe" if WINDOWS else "ffmpeg")),
     "tools/bin/ffmpeg"),
    (str(RAIZ / "tools" / "bin" / "ffmpeg" / "LICENSE.txt"), "tools/bin/ffmpeg"),
]

a = Analysis(
    [str(RAIZ / "empacotamento" / "iniciar.py")],
    pathex=[str(RAIZ / "src")],
    datas=dados,
    hiddenimports=["pillow_heif"],
    excludes=[
        # Módulos do Qt/Python que o app não usa (deixa o pacote bem menor).
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick",
        "PySide6.QtQml", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest", "tkinter", "unittest", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ags-media-chrono",
    console=False,
    icon=str(PACOTE / "recursos" / ("icone.ico" if WINDOWS else "icone.png")),
)
coll = COLLECT(exe, a.binaries, a.datas, name="ags-media-chrono")
