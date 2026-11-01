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
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono import APP_NAME, __version__
from ags_media_chrono.core.midias import TipoMidia
from ags_media_chrono.ui.carregador import CarregadorPasta
from ags_media_chrono.ui.filtro_galeria import Ordenacao, ProxyGaleria
from ags_media_chrono.ui.galeria import (
    PASSO_ZOOM,
    TAMANHO_MAX,
    TAMANHO_MIN,
    TAMANHO_PADRAO,
    VisaoGaleria,
)
from ags_media_chrono.ui.gerador_miniaturas import GeradorMiniaturas
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
    """Barra de filtros/ordenação + grade de mídias, com estado vazio quando não há pasta."""

    abrir_pasta = Signal()
    filtro_alterado = Signal()

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

        # Página 1: barra + grade de miniaturas
        self.modelo = ModeloMidias(self)
        self.proxy = ProxyGaleria(self)
        self.proxy.setSourceModel(self.modelo)
        self.grade = VisaoGaleria()
        self.grade.setModel(self.proxy)

        pagina = QWidget()
        pagina_layout = QVBoxLayout(pagina)
        pagina_layout.setContentsMargins(0, 0, 0, 0)
        pagina_layout.setSpacing(0)
        pagina_layout.addWidget(self._criar_barra())
        pagina_layout.addWidget(self.grade)
        self.pilha.addWidget(pagina)

    def _criar_barra(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("barraGaleria")
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.grupo_tipo = QButtonGroup(self)
        for rotulo, tipo in (
            ("Todos", None),
            ("Fotos", TipoMidia.FOTO),
            ("Vídeos", TipoMidia.VIDEO),
        ):
            botao = QToolButton()
            botao.setText(rotulo)
            botao.setCheckable(True)
            botao.setObjectName("segmento")
            botao.setProperty("tipo", tipo)
            botao.setChecked(tipo is None)
            self.grupo_tipo.addButton(botao)
            layout.addWidget(botao)
        self.grupo_tipo.buttonClicked.connect(self._ao_mudar_tipo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Filtrar por nome…")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMaximumWidth(260)
        self.busca.textChanged.connect(self._ao_mudar_texto)
        layout.addSpacing(6)
        layout.addWidget(self.busca)
        layout.addStretch(1)

        rotulo = QLabel("Ordenar por")
        rotulo.setObjectName("vazio")
        layout.addWidget(rotulo)
        self.combo_ordem = QComboBox()
        for ordenacao in Ordenacao:
            self.combo_ordem.addItem(ordenacao.rotulo, ordenacao)
        self.combo_ordem.currentIndexChanged.connect(self._ao_mudar_ordem)
        layout.addWidget(self.combo_ordem)

        self.botao_direcao = QToolButton()
        self.botao_direcao.setCheckable(True)  # marcado = decrescente
        self.botao_direcao.setText("↑")
        self.botao_direcao.setToolTip("Crescente / decrescente")
        self.botao_direcao.toggled.connect(self._ao_mudar_ordem)
        layout.addWidget(self.botao_direcao)
        return barra

    def _ao_mudar_tipo(self, botao: QToolButton) -> None:
        self.proxy.definir_tipo(botao.property("tipo"))
        self.filtro_alterado.emit()

    def _ao_mudar_texto(self, texto: str) -> None:
        self.proxy.definir_texto(texto)
        self.filtro_alterado.emit()

    def _ao_mudar_ordem(self, *_args) -> None:
        decrescente = self.botao_direcao.isChecked()
        self.botao_direcao.setText("↓" if decrescente else "↑")
        self.proxy.ordenar(self.combo_ordem.currentData(), crescente=not decrescente)

    def selecionar_tipo(self, tipo: TipoMidia | None) -> None:
        for botao in self.grupo_tipo.buttons():
            if botao.property("tipo") == tipo:
                botao.click()

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
        self._carregando = False

        self.painel_pastas = PainelPastas()
        self.galeria = AreaGaleria()
        self.painel_datas = PainelDatas()
        self.carregador = CarregadorPasta(self)
        self.carregador.lote.connect(self._ao_receber_lote)
        self.carregador.concluido.connect(self._ao_concluir)
        self.gerador = GeradorMiniaturas(self)
        self.gerador.pronta.connect(self._ao_receber_miniatura)
        self.galeria.grade.delegado.solicitar_miniatura = self.gerador.solicitar

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
        self._criar_barra_status()

        self.painel_pastas.pasta_selecionada.connect(self.abrir_pasta)
        self.galeria.abrir_pasta.connect(self.escolher_pasta)
        self.galeria.filtro_alterado.connect(self._atualizar_status)
        self.galeria.grade.selectionModel().selectionChanged.connect(self._atualizar_status)
        self.galeria.grade.tamanho_alterado.connect(self._sincronizar_zoom)

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

        self.acao_selecionar_tudo = QAction("Selecionar tudo", self)
        self.acao_selecionar_tudo.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.acao_selecionar_tudo.triggered.connect(self.galeria.grade.selectAll)

        self.acao_limpar_selecao = QAction("Limpar seleção", self)
        self.acao_limpar_selecao.setShortcut("Ctrl+Shift+A")
        self.acao_limpar_selecao.triggered.connect(self.galeria.grade.clearSelection)

        self.acao_zoom_mais = QAction("Aumentar miniaturas", self)
        self.acao_zoom_mais.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        self.acao_zoom_mais.triggered.connect(lambda: self._zoom_relativo(+1))
        self.acao_zoom_menos = QAction("Diminuir miniaturas", self)
        self.acao_zoom_menos.setShortcut("Ctrl+-")
        self.acao_zoom_menos.triggered.connect(lambda: self._zoom_relativo(-1))
        self.acao_zoom_padrao = QAction("Tamanho padrão", self)
        self.acao_zoom_padrao.setShortcut("Ctrl+0")
        self.acao_zoom_padrao.triggered.connect(
            lambda: self.galeria.grade.definir_tamanho(TAMANHO_PADRAO)
        )

        self.acoes_tipo = []
        for rotulo, tipo, atalho in (
            ("Mostrar todos", None, "Ctrl+1"),
            ("Só fotos", TipoMidia.FOTO, "Ctrl+2"),
            ("Só vídeos", TipoMidia.VIDEO, "Ctrl+3"),
        ):
            acao = QAction(rotulo, self)
            acao.setShortcut(atalho)
            acao.triggered.connect(lambda _=False, t=tipo: self.galeria.selecionar_tipo(t))
            self.acoes_tipo.append(acao)

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
        editar.addAction(self.acao_selecionar_tudo)
        editar.addAction(self.acao_limpar_selecao)
        editar.addSeparator()
        editar.addAction(self.acao_aplicar)
        editar.addAction(self.acao_renomear)

        exibir = menu.addMenu("E&xibir")
        exibir.addAction(self.acao_subpastas)
        exibir.addSeparator()
        exibir.addActions(self.acoes_tipo)
        exibir.addSeparator()
        exibir.addAction(self.acao_zoom_mais)
        exibir.addAction(self.acao_zoom_menos)
        exibir.addAction(self.acao_zoom_padrao)

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

    def _criar_barra_status(self) -> None:
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(TAMANHO_MIN, TAMANHO_MAX)
        self.slider_zoom.setValue(self.galeria.grade.tamanho)
        self.slider_zoom.setFixedWidth(150)
        self.slider_zoom.setToolTip("Tamanho das miniaturas (Ctrl + roda do mouse)")
        self.slider_zoom.valueChanged.connect(self.galeria.grade.definir_tamanho)
        self.statusBar().addPermanentWidget(self.slider_zoom)
        self.statusBar().showMessage("Pronto")

    def _sincronizar_zoom(self, tamanho: int) -> None:
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(tamanho)
        self.slider_zoom.blockSignals(False)

    def _zoom_relativo(self, passos: int) -> None:
        grade = self.galeria.grade
        grade.definir_tamanho(grade.tamanho + passos * PASSO_ZOOM * 2)

    def _atualizar_status(self, *_args) -> None:
        if self.pasta_atual is None or self._carregando:
            return
        modelo, proxy = self.galeria.modelo, self.galeria.proxy
        if modelo.rowCount() == 0:
            self.statusBar().showMessage(f"{self.pasta_atual} — vazio")
            return
        c = modelo.contagem()
        partes = [
            f"{_plural(c[TipoMidia.FOTO], 'foto', 'fotos')} · "
            f"{_plural(c[TipoMidia.VIDEO], 'vídeo', 'vídeos')}"
        ]
        if proxy.filtrando:
            partes.append(f"exibindo {proxy.rowCount():,}".replace(",", "."))
        selecionados = len(self.galeria.grade.selectionModel().selectedIndexes())
        if selecionados:
            partes.append(_plural(selecionados, "selecionado", "selecionados"))
        partes.append(str(self.pasta_atual))
        self.statusBar().showMessage(" — ".join(partes))

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
        self._carregando = True
        self.gerador.nova_geracao()
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
        self._carregando = False
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
        self.gerador.pre_carregar(self.galeria.modelo.midias())
        self._atualizar_status()

    def _ao_receber_miniatura(self, geracao: int, caminho: Path, imagem, duracao) -> None:
        if geracao != self.gerador.geracao:
            return
        self.galeria.modelo.definir_miniatura(caminho, imagem)
        if duracao:
            self.galeria.modelo.definir_duracao(caminho, duracao)

    def closeEvent(self, evento) -> None:
        self.carregador.cancelar()
        self.carregador.aguardar(2000)
        self.gerador.fechar()
        super().closeEvent(evento)

    def _sobre(self) -> None:
        QMessageBox.about(
            self,
            f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Organize as datas de fotos e vídeos e renomeie em lote.<br><br>"
            "Usa ExifTool (Phil Harvey), FFmpeg e Qt.",
        )
