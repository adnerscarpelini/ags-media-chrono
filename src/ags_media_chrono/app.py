"""Ponto de entrada da aplicação."""

import sys

from PySide6.QtWidgets import QApplication

from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.ui.main_window import MainWindow


def create_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("AGS")
    return app


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.show()
    return app.exec()
