"""Janela principal: pastas | galeria | datas."""

from pathlib import Path

from PySide6.QtCore import QDir, QModelIndex, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono import APP_NAME, __version__


def _titulo_painel(texto: str) -> QLabel:
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("tituloPainel")
    return rotulo


class PainelPastas(QFrame):
    pasta_selecionada = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("painel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_titulo_painel("Pastas"))

        self.modelo = QFileSystemModel(self)
        self.modelo.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.modelo.setRootPath("")

        self.arvore = QTreeView()
        self.arvore.setModel(self.modelo)
        self.arvore.setHeaderHidden(True)
        for coluna in range(1, self.modelo.columnCount()):
            self.arvore.hideColumn(coluna)
        self.arvore.setAnimated(True)
        self.arvore.setIndentation(14)
        self.arvore.clicked.connect(self._ao_clicar)
        layout.addWidget(self.arvore)

    def _ao_clicar(self, indice: QModelIndex) -> None:
        self.pasta_selecionada.emit(Path(self.modelo.filePath(indice)))

    def mostrar(self, pasta: Path) -> None:
        indice = self.modelo.index(str(pasta))
        self.arvore.setCurrentIndex(indice)
        self.arvore.scrollTo(indice)
        self.arvore.expand(indice)


class AreaGaleria(QFrame):
    """Placeholder da galeria; a grade de miniaturas chega nas issues #6–#9."""

    abrir_pasta = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("galeria")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.titulo = QLabel("Nenhuma pasta aberta")
        self.titulo.setObjectName("vazioTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitulo = QLabel("Escolha uma pasta à esquerda ou clique em Abrir pasta.")
        self.subtitulo.setObjectName("vazio")
        self.subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.botao = QPushButton("Abrir pasta…")
        self.botao.setObjectName("primario")
        self.botao.clicked.connect(self.abrir_pasta)

        layout.addWidget(self.titulo)
        layout.addWidget(self.subtitulo)
        layout.addWidget(self.botao, alignment=Qt.AlignmentFlag.AlignCenter)

    def mostrar_pasta(self, pasta: Path) -> None:
        self.titulo.setText(pasta.name or str(pasta))
        self.subtitulo.setText(str(pasta))
        self.botao.hide()


class PainelDatas(QFrame):
    """Placeholder do painel de datas; conteúdo real na issue #14."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("painel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(_titulo_painel("Datas do arquivo"))

        vazio = QLabel("Selecione um arquivo para ver\ntodas as datas encontradas.")
        vazio.setObjectName("vazio")
        vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(vazio, 1)

        rodape = QWidget()
        rodape_layout = QVBoxLayout(rodape)
        rodape_layout.setContentsMargins(10, 10, 10, 10)
        self.botao_aplicar = QPushButton("Aplicar datas")
        self.botao_aplicar.setObjectName("primario")
        self.botao_aplicar.setEnabled(False)
        rodape_layout.addWidget(self.botao_aplicar)
        layout.addWidget(rodape)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1400, 860)
        self.setMinimumSize(900, 560)
        self.pasta_atual: Path | None = None

        self.painel_pastas = PainelPastas()
        self.galeria = AreaGaleria()
        self.painel_datas = PainelDatas()

        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setHandleWidth(1)
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self.painel_pastas)
        self.divisor.addWidget(self.galeria)
        self.divisor.addWidget(self.painel_datas)
        self.divisor.setStretchFactor(0, 0)
        self.divisor.setStretchFactor(1, 1)
        self.divisor.setStretchFactor(2, 0)
        self.painel_pastas.setMinimumWidth(180)
        self.painel_datas.setMinimumWidth(280)
        self.divisor.setSizes([260, 800, 340])
        self.setCentralWidget(self.divisor)

        self._criar_acoes()
        self._criar_menus()
        self._criar_barra_ferramentas()
        self.statusBar().showMessage("Pronto")

        self.painel_pastas.pasta_selecionada.connect(self.abrir_pasta)
        self.galeria.abrir_pasta.connect(self.escolher_pasta)

    def _criar_acoes(self) -> None:
        self.acao_abrir = QAction("Abrir pasta…", self)
        self.acao_abrir.setShortcut(QKeySequence.StandardKey.Open)
        self.acao_abrir.triggered.connect(self.escolher_pasta)

        self.acao_aplicar = QAction("Aplicar datas", self)
        self.acao_aplicar.setShortcut("Ctrl+Return")
        self.acao_aplicar.setEnabled(False)

        self.acao_renomear = QAction("Renomear em lote…", self)
        self.acao_renomear.setShortcut("F2")
        self.acao_renomear.setEnabled(False)

        self.acao_sair = QAction("Sair", self)
        self.acao_sair.setShortcut(QKeySequence.StandardKey.Quit)
        self.acao_sair.triggered.connect(self.close)

        self.acao_sobre = QAction("Sobre", self)
        self.acao_sobre.triggered.connect(self._sobre)

    def _criar_menus(self) -> None:
        menu = self.menuBar()
        arquivo = menu.addMenu("&Arquivo")
        arquivo.addAction(self.acao_abrir)
        arquivo.addSeparator()
        arquivo.addAction(self.acao_sair)

        editar = menu.addMenu("&Editar")
        editar.addAction(self.acao_aplicar)
        editar.addAction(self.acao_renomear)

        ajuda = menu.addMenu("Aj&uda")
        ajuda.addAction(self.acao_sobre)

    def _criar_barra_ferramentas(self) -> None:
        barra = self.addToolBar("Principal")
        barra.setObjectName("barraPrincipal")
        barra.setMovable(False)
        barra.addAction(self.acao_abrir)
        barra.addSeparator()
        barra.addAction(self.acao_aplicar)
        barra.addAction(self.acao_renomear)

    def escolher_pasta(self) -> None:
        inicial = str(self.pasta_atual or Path.home())
        pasta = QFileDialog.getExistingDirectory(self, "Abrir pasta", inicial)
        if pasta:
            self.abrir_pasta(Path(pasta))

    def abrir_pasta(self, pasta: Path) -> None:
        self.pasta_atual = pasta
        self.painel_pastas.mostrar(pasta)
        self.galeria.mostrar_pasta(pasta)
        self.setWindowTitle(f"{pasta.name or pasta} — {APP_NAME}")
        self.statusBar().showMessage(str(pasta))

    def _sobre(self) -> None:
        QMessageBox.about(
            self,
            f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Organize as datas de fotos e vídeos e renomeie em lote.<br><br>"
            "Usa ExifTool (Phil Harvey), FFmpeg e Qt.",
        )
