"""Janela principal: pastas | galeria | datas."""

from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
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
from ags_media_chrono.core.escolhas import Status
from ags_media_chrono.core.gravacao import OpcoesGravacao
from ags_media_chrono.core.historico import Operacao, TipoOperacao, listar_operacoes
from ags_media_chrono.core.midias import TipoMidia
from ags_media_chrono.core.renomear import desfazer_renomeacao, entrada_para, renomear
from ags_media_chrono.ui.aplicacao import (
    DialogoAplicar,
    DialogoHistorico,
    DialogoRelatorio,
    TrabalhoGravacao,
    descrever_operacao,
    dialogo_progresso,
)
from ags_media_chrono.ui.carregador import CarregadorPasta
from ags_media_chrono.ui.dialogo_regra import DialogoRegra
from ags_media_chrono.ui.dialogo_renomear import DialogoRenomear
from ags_media_chrono.ui.filtro_galeria import Ordenacao, ProxyGaleria
from ags_media_chrono.ui.galeria import (
    PASSO_ZOOM,
    TAMANHO_MAX,
    TAMANHO_MIN,
    TAMANHO_PADRAO,
    VisaoGaleria,
)
from ags_media_chrono.ui.gerador_miniaturas import GeradorMiniaturas
from ags_media_chrono.ui.leitor_datas import LeitorDatas
from ags_media_chrono.ui.modelo_midias import ModeloMidias, PapelMidia
from ags_media_chrono.ui.painel_datas import PainelDatas
from ags_media_chrono.ui.visualizador import Visualizador


def _titulo_painel(texto: str) -> QLabel:
    rotulo = QLabel(texto.upper())
    rotulo.setObjectName("tituloPainel")
    return rotulo


def resumo_status(contagem: dict) -> str:
    """{Status.PENDENTE: 2, Status.SUGERIDA: 1, ...} -> "2 pendentes, 1 sugerida"."""
    nomes = {
        Status.PENDENTE: ("pendente", "pendentes"),
        Status.SUGERIDA: ("sugerida", "sugeridas"),
        Status.ESCOLHIDA: ("escolhida", "escolhidas"),
        Status.APLICADO: ("aplicado", "aplicados"),
        Status.ERRO: ("com erro", "com erro"),
    }
    return ", ".join(_plural(contagem[s], *nomes[s]) for s in Status if contagem.get(s))


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
        self.combo_status = QComboBox()
        self.combo_status.addItem("Todos os status", None)
        for status in Status:
            self.combo_status.addItem(status.rotulo, status.value)
        self.combo_status.setToolTip("Filtrar pelo status da data")
        self.combo_status.currentIndexChanged.connect(self._ao_mudar_status)
        layout.addWidget(self.combo_status)
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

    def _ao_mudar_status(self, _indice: int) -> None:
        valor = self.combo_status.currentData()
        self.proxy.definir_status(Status(valor) if valor else None)
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
        self.leitor = LeitorDatas(self)
        self.leitor.lote.connect(self._ao_receber_datas)
        self.leitor.falhou.connect(self._ao_falhar_leitura)
        self.painel_datas.opcoes_fuso = self.galeria.modelo.opcoes_fuso
        self.painel_datas.escolha_alterada.connect(self._ao_escolher)
        self.painel_datas.deslocamento_em_lote.connect(self._deslocar_selecionados)
        self.painel_datas.aplicar_solicitado.connect(self.aplicar_datas)
        self.trabalho = TrabalhoGravacao(self)
        self.trabalho.progresso.connect(self._ao_progresso)
        self.trabalho.terminado.connect(self._ao_terminar_trabalho)
        self._progresso = None
        self._tipo_trabalho: str | None = None
        self._renomear_depois = False
        self.relatorio: DialogoRelatorio | None = None

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
        self.galeria.grade.activated.connect(self.visualizar)  # duplo clique ou Enter
        selecao = self.galeria.grade.selectionModel()
        selecao.currentChanged.connect(self._atualizar_painel)
        selecao.selectionChanged.connect(self._atualizar_painel)

    def visualizar(self, indice: QModelIndex | None = None) -> Visualizador | None:
        grade = self.galeria.grade
        indice = indice if indice is not None and indice.isValid() else grade.currentIndex()
        if not indice.isValid():
            return None
        visualizador = Visualizador(grade.model(), indice.row(), self.gerador.obter_exiftool, self)
        # A galeria acompanha o item exibido, para ficar nele ao fechar o visualizador.
        visualizador.indice_alterado.connect(self._focar_item)
        visualizador.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        visualizador.showMaximized()
        return visualizador

    def _focar_item(self, indice: QModelIndex) -> None:
        grade = self.galeria.grade
        grade.setCurrentIndex(indice)
        grade.scrollTo(indice)

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
        self.acao_aplicar.triggered.connect(lambda: self.aplicar_datas())

        self.acao_aplicar_renomear = QAction("Aplicar datas e renomear…", self)
        self.acao_aplicar_renomear.setShortcut("Ctrl+Shift+Return")
        self.acao_aplicar_renomear.setEnabled(False)
        self.acao_aplicar_renomear.triggered.connect(
            lambda: self.aplicar_datas(renomear_depois=True)
        )

        self.acao_desfazer = QAction("Desfazer última aplicação", self)
        self.acao_desfazer.setShortcut(QKeySequence.StandardKey.Undo)
        self.acao_desfazer.triggered.connect(lambda: self.desfazer_ultima())
        self.acao_historico = QAction("Histórico de alterações…", self)
        self.acao_historico.setShortcut("Ctrl+H")
        self.acao_historico.triggered.connect(self.abrir_historico)

        self.acao_regra = QAction("Escolher data por regra…", self)
        self.acao_regra.setShortcut("Ctrl+R")
        self.acao_regra.setToolTip("Escolhe a data de vários arquivos de uma vez, por prioridade")
        self.acao_regra.triggered.connect(self.escolher_por_regra)

        self.acao_renomear = QAction("Renomear em lote…", self)
        self.acao_renomear.setShortcut("F2")
        self.acao_renomear.setEnabled(False)
        self.acao_renomear.triggered.connect(lambda: self.renomear_em_lote())

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
        editar.addAction(self.acao_desfazer)
        editar.addAction(self.acao_historico)
        editar.addSeparator()
        editar.addAction(self.acao_selecionar_tudo)
        editar.addAction(self.acao_limpar_selecao)
        editar.addSeparator()
        editar.addAction(self.acao_regra)
        editar.addAction(self.acao_aplicar)
        editar.addAction(self.acao_aplicar_renomear)
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
        barra.addAction(self.acao_regra)
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
        self.acao_renomear.setEnabled(modelo.rowCount() > 0)
        c = modelo.contagem()
        partes = [
            f"{_plural(c[TipoMidia.FOTO], 'foto', 'fotos')} · "
            f"{_plural(c[TipoMidia.VIDEO], 'vídeo', 'vídeos')}"
        ]
        if proxy.filtrando:
            partes.append(f"exibindo {proxy.rowCount():,}".replace(",", "."))
        selecionados = len(self.galeria.grade.selectionModel().selectedIndexes())
        resumo = resumo_status(modelo.contagem_status())
        if resumo:
            partes.append(resumo)
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
        self.leitor.nova_geracao()
        self.painel_datas.limpar()
        self.galeria.modelo.limpar()
        self.galeria.mostrar_vazio("Carregando…", str(self.pasta_atual), botao=False)
        self.statusBar().showMessage(f"Carregando {self.pasta_atual}…")
        self.carregador.carregar(self.pasta_atual, self.acao_subpastas.isChecked())

    def _ao_receber_lote(self, geracao: int, midias: list) -> None:
        if geracao != self.carregador.geracao:
            return
        self.galeria.modelo.adicionar(midias)
        self.leitor.ler([m.caminho for m in midias])
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

    # --- datas ---------------------------------------------------------------------------------

    def _arquivo_em_foco(self) -> Path | None:
        indice = self.galeria.grade.currentIndex()
        return indice.data(PapelMidia).caminho if indice.isValid() else None

    def _atualizar_painel(self, *_args) -> None:
        arquivo = self._arquivo_em_foco()
        if arquivo is None:
            self.painel_datas.limpar()
            return
        estado = self.galeria.modelo.estado(arquivo)
        if not estado.lido:
            self.leitor.ler_agora(arquivo)
        selecionados = len(self.galeria.grade.selectionModel().selectedIndexes())
        self.painel_datas.mostrar(arquivo, estado, max(1, selecionados))
        self._atualizar_botao_aplicar()

    def _ao_receber_datas(self, geracao: int, lista: list) -> None:
        if geracao != self.leitor.geracao:
            return
        modelo = self.galeria.modelo
        for datas in lista:
            modelo.definir_datas(datas)
        self._atualizar_status()
        foco = self._arquivo_em_foco()
        if foco is not None and any(d.arquivo == foco for d in lista):
            self._atualizar_painel()
        self._atualizar_botao_aplicar()

    def _ao_falhar_leitura(self, geracao: int, mensagem: str) -> None:
        if geracao == self.leitor.geracao:
            self.statusBar().showMessage(f"Erro ao ler datas: {mensagem}", 10_000)

    def _ao_escolher(self, arquivo: Path, escolha) -> None:
        modelo = self.galeria.modelo
        modelo.definir_escolha(arquivo, escolha)
        self.painel_datas.ao_estado_alterado(modelo.estado(arquivo))
        self._atualizar_status()
        self._atualizar_botao_aplicar()

    def _deslocar_selecionados(self, deslocamento) -> None:
        modelo = self.galeria.modelo
        alterados = 0
        for caminho in self.arquivos_alvo():
            escolha = modelo.estado(caminho).escolha
            if escolha is not None:
                modelo.definir_escolha(caminho, escolha.com_deslocamento(deslocamento))
                alterados += 1
        self.statusBar().showMessage(f"Ajuste aplicado a {alterados} arquivo(s).", 8000)
        self._atualizar_painel()

    def _atualizar_botao_aplicar(self) -> None:
        prontos = self.arquivos_prontos()
        self.painel_datas.botao_aplicar.setEnabled(bool(prontos))
        self.acao_aplicar.setEnabled(bool(prontos))
        self.acao_aplicar_renomear.setEnabled(bool(prontos))
        rotulo = f"Aplicar datas ({len(prontos)})" if prontos else "Aplicar datas"
        self.painel_datas.botao_aplicar.setText(rotulo)

    def arquivos_alvo(self) -> list[Path]:
        """Arquivos selecionados; se nenhum estiver selecionado, todos os exibidos."""
        grade = self.galeria.grade
        indices = grade.selectionModel().selectedIndexes()
        if not indices:
            modelo = grade.model()
            indices = [modelo.index(i, 0) for i in range(modelo.rowCount())]
        return [i.data(PapelMidia).caminho for i in indices]

    def escolher_por_regra(self) -> None:
        modelo = self.galeria.modelo
        alvos = self.arquivos_alvo()
        if not alvos:
            return
        estados = {c: modelo.estado(c) for c in alvos}
        dialogo = DialogoRegra(estados, modelo.opcoes_fuso, parent=self)
        if not dialogo.exec() or dialogo.resultado is None:
            return
        for caminho, escolha in dialogo.resultado.escolhas.items():
            modelo.definir_escolha(caminho, escolha)
        r = dialogo.resultado
        self.statusBar().showMessage(
            f"Regra aplicada: {len(r.escolhas)} com data escolhida, "
            f"{len(r.sem_data)} sem data encontrada.",
            10_000,
        )
        self._atualizar_painel()

    def arquivos_prontos(self) -> list[Path]:
        """Arquivos selecionados (ou todos, se nenhum) com data pronta para gravar."""
        grade, modelo = self.galeria.grade, self.galeria.modelo
        indices = grade.selectionModel().selectedIndexes()
        if indices:
            caminhos = [i.data(PapelMidia).caminho for i in indices]
        else:
            caminhos = [m.caminho for m in modelo.midias()]
        return [c for c in caminhos if modelo.estado(c).status.pronto_para_aplicar]

    # --- gravação, desfazer e histórico ---------------------------------------------------

    def aplicar_datas(
        self, opcoes: OpcoesGravacao | None = None, renomear_depois: bool = False
    ) -> bool:
        """Grava as datas dos arquivos prontos. Sem `opcoes`, pergunta ao usuário.
        Com `renomear_depois`, abre o Renomear em lote com os arquivos gravados (issue #29)."""
        if self._tipo_trabalho is not None:
            return False
        modelo = self.galeria.modelo
        prontos = self.arquivos_prontos()
        if not prontos:
            return False
        if opcoes is None:
            dialogo = DialogoAplicar(
                len(prontos), modelo.opcoes_fuso.quicktime_utc, renomear_depois, self
            )
            if not dialogo.exec():
                return False
            opcoes = dialogo.opcoes()
            renomear_depois = dialogo.caixa_renomear.isChecked()
        self._renomear_depois = renomear_depois
        itens = [(modelo.midia_por_caminho(c), modelo.estado(c).escolha.final) for c in prontos]
        self._iniciar_trabalho("gravar", "Gravando datas…", len(itens))
        self.trabalho.gravar(itens, opcoes)
        return True

    def desfazer_ultima(self, confirmar: bool = True) -> bool:
        pendente = next((op for op in listar_operacoes() if not op.desfeita), None)
        if pendente is None:
            QMessageBox.information(self, "Desfazer", "Não há alterações para desfazer.")
            return False
        return self.desfazer(pendente, confirmar)

    def abrir_historico(self) -> None:
        dialogo = DialogoHistorico(self)
        if dialogo.exec() and dialogo.operacao_escolhida is not None:
            self.desfazer(dialogo.operacao_escolhida)

    def desfazer(self, operacao: Operacao, confirmar: bool = True) -> bool:
        if self._tipo_trabalho is not None or operacao.desfeita:
            return False
        if confirmar:
            resposta = QMessageBox.question(
                self, "Desfazer", f"Desfazer esta operação?\n\n{descrever_operacao(operacao)}"
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return False
        if operacao.tipo == TipoOperacao.DATAS:
            self._iniciar_trabalho("desfazer", "Desfazendo…", operacao.quantidade_ok)
            self.trabalho.desfazer(operacao)
            return True
        return self._desfazer_renomeacao(operacao)

    def renomear_em_lote(self, dialogo: DialogoRenomear | None = None) -> bool:
        """Abre o diálogo para os selecionados (ou todos os exibidos) e renomeia."""
        return self.renomear_arquivos(self.arquivos_alvo(), dialogo)

    def renomear_arquivos(self, alvos: list[Path], dialogo: DialogoRenomear | None = None) -> bool:
        modelo = self.galeria.modelo
        if not alvos or self._tipo_trabalho is not None:
            return False
        if dialogo is None:
            itens = [
                entrada_para(modelo.midia_por_caminho(c), modelo.estado(c), modelo.opcoes_fuso)
                for c in alvos
            ]
            dialogo = DialogoRenomear(itens, self)
            if not dialogo.exec():
                return False
        resultado = renomear(dialogo.plano)
        if resultado.erro is not None:
            QMessageBox.warning(self, "Renomear", f"Nada foi renomeado:\n{resultado.erro}")
            return False
        for e in resultado.operacao.entradas:
            modelo.renomear(Path(e["de"]), Path(e["para"]))
        self.statusBar().showMessage(
            f"{len(resultado.operacao.entradas)} arquivo(s) renomeado(s). "
            "Para desfazer: Editar › Desfazer (Ctrl+Z).",
            10_000,
        )
        self._atualizar_painel()
        return True

    def _desfazer_renomeacao(self, operacao: Operacao) -> bool:
        erro = desfazer_renomeacao(operacao)
        if erro is not None:
            QMessageBox.warning(self, "Desfazer", f"Não foi possível desfazer:\n{erro}")
            return False
        for e in operacao.entradas:
            if e.get("ok"):
                self.galeria.modelo.renomear(Path(e["para"]), Path(e["de"]))
        self.statusBar().showMessage("Renomeação desfeita.", 8000)
        self._atualizar_painel()
        return True

    def _iniciar_trabalho(self, tipo: str, titulo: str, total: int) -> None:
        self._tipo_trabalho = tipo
        self._progresso = dialogo_progresso(titulo, total, self)
        self._progresso.canceled.connect(self.trabalho.cancelar)
        self.acao_aplicar.setEnabled(False)
        self.painel_datas.botao_aplicar.setEnabled(False)

    def _ao_progresso(self, atual: int, total: int, nome: str) -> None:
        if self._progresso is not None:
            self._progresso.setMaximum(total)
            self._progresso.setValue(atual - 1)
            self._progresso.setLabelText(f"{nome}  ({atual} de {total})")

    def _ao_terminar_trabalho(self, resultado, cancelado: bool) -> None:
        tipo, self._tipo_trabalho = self._tipo_trabalho, None
        if self._progresso is not None:
            self._progresso.close()
            self._progresso = None
        self._atualizar_botao_aplicar()
        if isinstance(resultado, Exception):
            QMessageBox.critical(self, "Erro", f"A operação falhou:\n{resultado}")
            return
        modelo = self.galeria.modelo
        if tipo == "gravar":
            entradas = resultado.entradas
            for e in entradas:
                status = Status.APLICADO if e["ok"] else Status.ERRO
                modelo.definir_status(Path(e["arquivo"]), status, e.get("mensagem", ""))
            titulo = "Datas aplicadas"
        else:
            entradas = [r.para_entrada() for r in resultado]
            for e in entradas:
                if e["ok"]:
                    modelo.reiniciar_estado(Path(e["arquivo"]))
            titulo = "Alterações desfeitas"
        lidos = [Path(e["arquivo"]) for e in entradas if e["ok"]]
        if lidos:
            self.leitor.reler(lidos)
        self._atualizar_status()
        self._atualizar_painel()
        self.relatorio = DialogoRelatorio(titulo, entradas, cancelado, self)
        self.relatorio.open()
        if tipo == "gravar" and self._renomear_depois and lidos and not cancelado:
            self._renomear_depois = False
            # Depois do relatório aparecer; as datas escolhidas já são as gravadas.
            QTimer.singleShot(0, lambda: self.renomear_arquivos(lidos))

    def closeEvent(self, evento) -> None:
        self.trabalho.cancelar()
        self.trabalho.aguardar(10_000)
        self.carregador.cancelar()
        self.carregador.aguardar(2000)
        self.gerador.fechar()
        self.leitor.fechar()
        super().closeEvent(evento)

    def _sobre(self) -> None:
        QMessageBox.about(
            self,
            f"Sobre o {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Organize as datas de fotos e vídeos e renomeie em lote.<br><br>"
            "Usa ExifTool (Phil Harvey), FFmpeg e Qt.",
        )
