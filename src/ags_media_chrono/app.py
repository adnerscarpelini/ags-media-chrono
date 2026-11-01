"""Ponto de entrada da aplicação."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.core.ferramentas import ferramentas_ausentes
from ags_media_chrono.ui.main_window import MainWindow
from ags_media_chrono.ui.tema import aplicar_tema

RECURSOS = Path(__file__).resolve().parent / "recursos"


def _identificar_app_no_windows() -> None:
    """Faz a barra de tarefas do Windows mostrar o ícone do app (e não o do Python)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AGS.MediaChrono")


def create_app(argv: list[str] | None = None) -> QApplication:
    _identificar_app_no_windows()
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("AGS")
    app.setWindowIcon(QIcon(str(RECURSOS / "icone.png")))
    aplicar_tema(app)
    return app


def avisar_ferramentas_ausentes(parent: QWidget) -> None:
    if not (ausentes := ferramentas_ausentes()):
        return
    QMessageBox.warning(
        parent,
        "Ferramentas não encontradas",
        "Não foi possível localizar: " + ", ".join(ausentes) + ".\n\n"
        "Leitura/gravação de datas e miniaturas de vídeo não vão funcionar.\n\n"
        "Para instalar, rode na pasta do projeto:\n"
        "    python tools/baixar_ferramentas.py\n\n"
        "No Linux também é possível instalar pelo sistema "
        "(ex.: sudo apt install libimage-exiftool-perl ffmpeg).",
    )


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.show()
    avisar_ferramentas_ausentes(window)
    return app.exec()
