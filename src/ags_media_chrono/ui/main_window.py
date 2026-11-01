"""Janela principal: pastas | galeria | datas."""

from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QLabel,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.core.midias import TipoMidia
from ags_media_chrono.ui.carregador import CarregadorPasta
from ags_media_chrono.ui.modelo_midias import ModeloMidias


def _titulo_painel(texto: str) -> QLabel:
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("tituloPainel")
    return rotulo


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n:,}".replace(",", ".") + f" {singular if n == 1 else plural}"


class _FiltroPastasOcultas(QSortFilterProxyModel):
    """Esconde pastas que começam com '.' (no Linux o Qt já as oculta; no Windows não)."""

    def filterAcceptsRow(self, linha: int, pai: QModelIndex | QPersistentModelIndex) -> bool:
        modelo = self.sourceModel()
        return not modelo.fileName(modelo.index(linha, 0, pai)).startswith(".")


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
        self.filtro = _FiltroPastasOcultas(self)
        self.filtro.setSourceModel(self.modelo)

        self.arvore = QTreeView()
        self.arvore.setModel(self.filtro)
        self.arvore.setHeaderHidden(True)
        for coluna in range(1, self.modelo.columnCount()):
            self.arvore.hideColumn(coluna)
        self.arvore.setAnimated(True)
        self.arvore.setIndentation(14)
        self.arvore.clicked.connect(self._ao_clicar)
        layout.addWidget(self.arvore)

    def _ao_clicar(self, indice: QModelIndex) -> None:
        caminho = self.modelo.filePath(self.filtro.mapToSource(indice))
        self.pasta_selecionada.emit(Path(caminho))

    def mostrar(self, pasta: Path) -> None:
        indice = self.filtro.mapFromSource(self.modelo.index(str(pasta)))
        self.arvore.setCurrentIndex(indice)
        self.arvore.scrollTo(indice)
        self.arvore.expand(indice)


class AreaGaleria(QFrame):
    """Lista de mídias da pasta. A grade de miniaturas substitui a lista na issue #7."""

    abrir_pasta = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("galeria")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pilha = QStackedWidget()
        layout.addWidget(self.pilha)

        # Página 0: estado vazio
        vazio = QWidget()
        vazio_layout = QVBoxLayout(vazio)
        vazio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio_layout.setSpacing(10)
        self.titulo = QLabel("Nenhuma pasta aberta")
        self.titulo.setObjectName("vazioTitulo")
        self.titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitulo = QLabel("Escolha uma pasta à esquerda ou clique em Abrir pasta.")
        self.subtitulo.setObjectName("vazio")
        self.subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.botao = QPushButton("Abrir pasta…")
        self.botao.setObjectName("primario")
        self.botao.clicked.connect(self.abrir_pasta)
        vazio_layout.addWidget(self.titulo)
        vazio_layout.addWidget(self.subtitulo)
        vazio_layout.addWidget(self.botao, alignment=Qt.AlignmentFlag.AlignCenter)
        self.pilha.addWidget(vazio)

        # Página 1: lista de mídias
        self.modelo = ModeloMidias(self)
        self.lista = QListView()
        self.lista.setModel(self.modelo)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.setUniformItemSizes(True)
        self.lista.setObjectName("galeria")
        self.pilha.addWidget(self.lista)

    def mostrar_vazio(self, titulo: str, subtitulo: str, botao: bool) -> None:
        self.titulo.setText(titulo)
        self.subtitulo.setText(subtitulo)
        self.botao.setVisible(botao)
        self.pilha.setCurrentIndex(0)

    def mostrar_lista(self) -> None:
        self.pilha.setCurrentIndex(1)


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
        self.carregador = CarregadorPasta(self)
        self.carregador.lote.connect(self._ao_receber_lote)
        self.carregador.concluido.connect(self._ao_concluir)

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

        self.acao_subpastas = QAction("Incluir subpastas", self)
        self.acao_subpastas.setCheckable(True)
        self.acao_subpastas.setToolTip("Listar também as fotos e vídeos das subpastas")
        self.acao_subpastas.toggled.connect(self._recarregar)

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

        exibir = menu.addMenu("E&xibir")
        exibir.addAction(self.acao_subpastas)

        ajuda = menu.addMenu("Aj&uda")
        ajuda.addAction(self.acao_sobre)

    def _criar_barra_ferramentas(self) -> None:
        barra = self.addToolBar("Principal")
        barra.setObjectName("barraPrincipal")
        barra.setMovable(False)
        barra.addAction(self.acao_abrir)
        barra.addAction(self.acao_subpastas)
        barra.addSeparator()
        barra.addAction(self.acao_aplicar)
        barra.addAction(self.acao_renomear)

    # --- abrir pasta -------------------------------------------------------------------------

    def escolher_pasta(self) -> None:
        inicial = str(self.pasta_atual or Path.home())
        pasta = QFileDialog.getExistingDirectory(self, "Abrir pasta", inicial)
        if pasta:
            self.abrir_pasta(Path(pasta))

    def abrir_pasta(self, pasta: Path) -> None:
        self.pasta_atual = pasta
        self.painel_pastas.mostrar(pasta)
        self.setWindowTitle(f"{pasta.name or pasta} — {APP_NAME}")
        self._recarregar()

    def _recarregar(self) -> None:
        if self.pasta_atual is None:
            return
        self.galeria.modelo.limpar()
        self.galeria.mostrar_vazio("Carregando…", str(self.pasta_atual), botao=False)
        self.statusBar().showMessage(f"Carregando {self.pasta_atual}…")
        self.carregador.carregar(self.pasta_atual, self.acao_subpastas.isChecked())

    def _ao_receber_lote(self, geracao: int, midias: list) -> None:
        if geracao != self.carregador.geracao:
            return
        self.galeria.modelo.adicionar(midias)
        self.galeria.mostrar_lista()
        total = self.galeria.modelo.rowCount()
        self.statusBar().showMessage(f"Carregando… {_plural(total, 'arquivo', 'arquivos')}")

    def _ao_concluir(self, geracao: int, total: int) -> None:
        if geracao != self.carregador.geracao:
            return
        if total == 0:
            self.galeria.mostrar_vazio(
                "Nenhuma foto ou vídeo nesta pasta",
                "Marque “Incluir subpastas” para procurar também nas subpastas."
                if not self.acao_subpastas.isChecked()
                else str(self.pasta_atual),
                botao=False,
            )
            self.statusBar().showMessage(f"{self.pasta_atual} — vazio")
            return
        c = self.galeria.modelo.contagem()
        self.statusBar().showMessage(
            f"{_plural(c[TipoMidia.FOTO], 'foto', 'fotos')} · "
            f"{_plural(c[TipoMidia.VIDEO], 'vídeo', 'vídeos')} — {self.pasta_atual}"
        )

    def closeEvent(self, evento) -> None:
        self.carregador.cancelar()
        self.carregador.aguardar(2000)
        super().closeEvent(evento)

    def _sobre(self) -> None:
        QMessageBox.about(
            self,
            f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Organize as datas de fotos e vídeos e renomeie em lote.<br><br>"
            "Usa ExifTool (Phil Harvey), FFmpeg e Qt.",
        )
