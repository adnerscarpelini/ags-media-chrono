"""Tela "Sobre": versão, ferramentas encontradas e créditos/licenças de terceiros."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6 import __version__ as versao_pyside
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar

URL_PROJETO = "https://github.com/adnerscarpelini/ags-media-chrono"
LOGO = Path(__file__).resolve().parents[1] / "recursos" / "logo_sobre.png"
_SEM_JANELA = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

CREDITOS = (
    ("ExifTool", "Phil Harvey", "Perl Artistic License / GPL", "https://exiftool.org"),
    ("FFmpeg", "FFmpeg developers (build LGPL de BtbN)", "LGPL 2.1+", "https://ffmpeg.org"),
    ("Qt / PySide6", "The Qt Company", "LGPL 3", "https://www.qt.io"),
    ("Pillow", "Jeffrey A. Clark e colaboradores", "MIT-CMU", "https://python-pillow.org"),
    ("pillow-heif / libheif", "Alexander Piskun / struktur AG", "BSD-3 / LGPL 3",
     "https://github.com/bigcat88/pillow_heif"),
)  # fmt: skip


def versao_ferramenta(nome: str) -> str:
    """Versão da ferramenta encontrada, ou o motivo de não estar disponível."""
    try:
        caminho = localizar(nome)
    except FerramentaNaoEncontrada:
        return "não encontrado"
    argumento = "-ver" if nome == "exiftool" else "-version"
    try:
        saida = subprocess.run(
            [str(caminho), argumento], capture_output=True, text=True, timeout=10,
            creationflags=_SEM_JANELA,
        ).stdout  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return f"erro ao executar ({caminho})"
    primeira = saida.strip().splitlines()[0] if saida.strip() else "?"
    if nome != "exiftool":  # "ffmpeg version n8.1.3-... Copyright ..." -> "n8.1.3-..."
        partes = primeira.split()
        primeira = partes[2] if len(partes) > 2 else primeira
    return primeira


class DialogoSobre(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Sobre o {APP_NAME}")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)

        logo = QLabel()
        logo.setPixmap(QPixmap(str(LOGO)))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)

        exiftool, ffmpeg = versao_ferramenta("exiftool"), versao_ferramenta("ffmpeg")
        creditos = "".join(
            f"<li><a href='{url}'>{nome}</a> — {autor} ({licenca})</li>"
            for nome, autor, licenca, url in CREDITOS
        )
        texto = QLabel(
            f"<h2 style='margin-bottom:0'>{APP_NAME}</h2>"
            f"<p>Versão {__version__}</p>"
            "<p>Mostra todas as datas de fotos e vídeos, permite escolher a correta, "
            "gravá-la em todos os campos e renomear em lote.</p>"
            f"<p><a href='{URL_PROJETO}'>{URL_PROJETO}</a> — licença MIT</p>"
            f"<p><b>Ferramentas em uso:</b> ExifTool {exiftool} · FFmpeg {ffmpeg} · "
            f"PySide6 {versao_pyside} · Python {sys.version.split()[0]}</p>"
            f"<p><b>Software de terceiros:</b></p><ul>{creditos}</ul>"
        )
        texto.setWordWrap(True)
        texto.setOpenExternalLinks(True)
        texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(texto)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
