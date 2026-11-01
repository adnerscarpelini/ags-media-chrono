"""Janela principal. O layout completo (pastas | galeria | datas) vem na issue #5."""

from PySide6.QtWidgets import QMainWindow

from ags_media_chrono import APP_NAME, __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1280, 800)
