"""Visualização ampliada: foto em tela cheia (ajustada à janela) ou player de vídeo.

Navega pela ordem atual da galeria (respeitando ordenação e filtros). Atalhos:
←/→ anterior/próximo, Home/End primeiro/último, Espaço play/pause, F11 tela cheia, Esc fecha.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QRect,
    QSize,
    Qt,
    QThreadPool,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QImage, QKeyEvent, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.core.miniaturas import imagem_ampliada
from ags_media_chrono.ui.galeria import formatar_duracao
from ags_media_chrono.ui.modelo_midias import PapelMidia, PapelMiniatura

FUNDO = "#0e0e0e"


class TelaImagem(QWidget):
    """Desenha a imagem ajustada à área disponível (sem ampliar além do tamanho real)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.imagem: QImage | None = None
        self.mensagem = ""
        self.ampliar = False  # True para a prévia (miniatura) enquanto a imagem grande carrega
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def mostrar(self, imagem: QImage | None, mensagem: str = "", ampliar: bool = False) -> None:
        self.imagem = imagem
        self.mensagem = mensagem
        self.ampliar = ampliar
        self.update()

    def paintEvent(self, _evento) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(FUNDO))
        if self.imagem is not None and not self.imagem.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            area = self.rect().adjusted(16, 16, -16, -16)
            tamanho = self.imagem.size()
            cabe = tamanho.width() <= area.width() and tamanho.height() <= area.height()
            if self.ampliar or not cabe:
                tamanho = tamanho.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
            alvo = QRect(0, 0, tamanho.width(), tamanho.height())
            alvo.moveCenter(area.center())
            painter.drawImage(alvo, self.imagem)
        if self.mensagem:
            painter.setPen(QColor("#8c8c8c"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.mensagem)


class _Sinais(QObject):
    carregada = Signal(int, QImage)  # geração, imagem
    falhou = Signal(int, str)


class Visualizador(QDialog):
    indice_alterado = Signal(QModelIndex)  # para a galeria acompanhar o item exibido

    def __init__(
        self,
        modelo: QAbstractItemModel,
        linha: int,
        obter_exiftool: Callable[[], ExifTool | None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("visualizador")
        self.setWindowTitle("Visualizar")
        self.setStyleSheet(
            f"QDialog#visualizador {{ background: {FUNDO}; }}"
            "QDialog#visualizador QToolButton { font-size: 16px; padding: 2px 10px; }"
        )
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        self.modelo = modelo
        self.linha = linha
        self._obter_exiftool = obter_exiftool or (lambda: None)
        self._geracao = 0
        self._sinais = _Sinais(self)
        self._sinais.carregada.connect(self._ao_carregar)
        self._sinais.falhou.connect(self._ao_falhar)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._criar_topo())

        self.pilha = QStackedWidget()
        self.tela = TelaImagem()
        self.video = QVideoWidget()
        self.video.setStyleSheet(f"background: {FUNDO};")
        self.pilha.addWidget(self.tela)
        self.pilha.addWidget(self.video)
        layout.addWidget(self.pilha, 1)
        layout.addWidget(self._criar_controles_video())

        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.positionChanged.connect(self._ao_mudar_posicao)
        self.player.durationChanged.connect(self._ao_mudar_duracao)
        self.player.playbackStateChanged.connect(self._atualizar_botao_play)

        self.resize(QSize(1280, 820))
        self.exibir(linha)

    # --- montagem -------------------------------------------------------------------------

    def _botao(self, texto: str, dica: str, acao: Callable[[], None]) -> QToolButton:
        botao = QToolButton()
        botao.setText(texto)
        botao.setToolTip(dica)
        botao.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # setas/Espaço ficam com o diálogo
        botao.clicked.connect(acao)
        return botao

    def _criar_topo(self) -> QFrame:
        topo = QFrame()
        topo.setObjectName("barraGaleria")
        layout = QHBoxLayout(topo)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self._botao("❮", "Anterior (←)", lambda: self.navegar(-1)))
        layout.addWidget(self._botao("❯", "Próximo (→)", lambda: self.navegar(+1)))
        self.rotulo_nome = QLabel()
        self.rotulo_nome.setStyleSheet("font-weight: 600; padding-left: 6px;")
        layout.addWidget(self.rotulo_nome, 1)
        self.rotulo_info = QLabel()
        self.rotulo_info.setObjectName("vazio")
        layout.addWidget(self.rotulo_info)
        layout.addWidget(self._botao("⛶", "Tela cheia (F11)", self.alternar_tela_cheia))
        layout.addWidget(self._botao("✕", "Fechar (Esc)", self.close))
        return topo

    def _criar_controles_video(self) -> QFrame:
        self.controles = QFrame()
        self.controles.setObjectName("barraGaleria")
        layout = QHBoxLayout(self.controles)
        layout.setContentsMargins(8, 4, 8, 6)
        self.botao_play = self._botao("", "Reproduzir/pausar (Espaço)", self.alternar_play)
        self.botao_play.setIcon(self._icone(QStyle.StandardPixmap.SP_MediaPause))
        layout.addWidget(self.botao_play)
        self.barra_posicao = QSlider(Qt.Orientation.Horizontal)
        self.barra_posicao.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.barra_posicao.sliderMoved.connect(lambda ms: self.player.setPosition(ms))
        layout.addWidget(self.barra_posicao, 1)
        self.rotulo_tempo = QLabel("0:00 / 0:00")
        self.rotulo_tempo.setObjectName("vazio")
        layout.addWidget(self.rotulo_tempo)
        self.botao_mudo = self._botao("", "Som ligado/desligado (M)", self.alternar_mudo)
        self.botao_mudo.setIcon(self._icone(QStyle.StandardPixmap.SP_MediaVolume))
        layout.addWidget(self.botao_mudo)
        return self.controles

    def _icone(self, padrao: QStyle.StandardPixmap) -> QIcon:
        return self.style().standardIcon(padrao)

    # --- navegação ------------------------------------------------------------------------

    @property
    def total(self) -> int:
        return self.modelo.rowCount()

    def midia_atual(self) -> Midia:
        return self.modelo.index(self.linha, 0).data(PapelMidia)

    def navegar(self, passo: int) -> None:
        self.exibir(max(0, min(self.total - 1, self.linha + passo)))

    def exibir(self, linha: int) -> None:
        if not 0 <= linha < self.total:
            return
        self.linha = linha
        self._geracao += 1
        indice = self.modelo.index(linha, 0)
        midia: Midia = indice.data(PapelMidia)
        self.rotulo_nome.setText(midia.nome)
        self.setWindowTitle(f"{midia.nome} — Visualizar")
        self.rotulo_info.setText(f"{linha + 1} / {self.total}")
        self.indice_alterado.emit(indice)

        self.player.stop()
        if midia.tipo == TipoMidia.VIDEO:
            self.pilha.setCurrentWidget(self.video)
            self.controles.show()
            self.player.setSource(QUrl.fromLocalFile(str(midia.caminho)))
            self.player.play()
        else:
            self.player.setSource(QUrl())
            self.pilha.setCurrentWidget(self.tela)
            self.controles.hide()
            # Mostra a miniatura na hora e troca pela imagem grande quando carregar.
            previa = indice.data(PapelMiniatura)
            self.tela.mostrar(previa, "" if previa is not None else "Carregando…", ampliar=True)
            self._carregar(midia)

    def _lado_max(self) -> int:
        tela = self.screen()
        tamanho = tela.size() * tela.devicePixelRatio()
        return max(tamanho.width(), tamanho.height())

    def _carregar(self, midia: Midia) -> None:
        geracao = self._geracao
        lado = self._lado_max()
        self._pool.clear()

        def trabalho() -> None:
            if geracao != self._geracao:
                return
            try:
                pil = imagem_ampliada(midia, lado, self._obter_exiftool())
                imagem = QImage(
                    pil.tobytes(), pil.width, pil.height, 3 * pil.width, QImage.Format.Format_RGB888
                ).copy()  # copia: os bytes do Pillow deixam de existir ao sair daqui
                self._sinais.carregada.emit(geracao, imagem)
            except Exception as e:  # noqa: BLE001 — qualquer falha vira mensagem na tela
                self._sinais.falhou.emit(geracao, str(e))

        self._pool.start(trabalho)

    def _ao_carregar(self, geracao: int, imagem: QImage) -> None:
        if geracao == self._geracao:
            self.tela.mostrar(imagem)
            self.rotulo_info.setText(
                f"{imagem.width()} × {imagem.height()}   {self.linha + 1} / {self.total}"
            )

    def _ao_falhar(self, geracao: int, mensagem: str) -> None:
        if geracao == self._geracao:
            self.tela.mostrar(
                self.tela.imagem, f"Não foi possível abrir a imagem\n{mensagem}", self.tela.ampliar
            )

    # --- vídeo ----------------------------------------------------------------------------

    def alternar_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def alternar_mudo(self) -> None:
        self.audio.setMuted(not self.audio.isMuted())
        mudo = QStyle.StandardPixmap.SP_MediaVolumeMuted
        som = QStyle.StandardPixmap.SP_MediaVolume
        self.botao_mudo.setIcon(self._icone(mudo if self.audio.isMuted() else som))

    def _atualizar_botao_play(self, estado) -> None:
        tocando = estado == QMediaPlayer.PlaybackState.PlayingState
        pausa, play = QStyle.StandardPixmap.SP_MediaPause, QStyle.StandardPixmap.SP_MediaPlay
        self.botao_play.setIcon(self._icone(pausa if tocando else play))

    def _ao_mudar_duracao(self, ms: int) -> None:
        self.barra_posicao.setRange(0, ms)
        self._ao_mudar_posicao(self.player.position())

    def _ao_mudar_posicao(self, ms: int) -> None:
        if not self.barra_posicao.isSliderDown():
            self.barra_posicao.setValue(ms)
        total = self.player.duration()
        self.rotulo_tempo.setText(
            f"{formatar_duracao(ms / 1000)} / {formatar_duracao(total / 1000)}"
        )

    # --- janela ---------------------------------------------------------------------------

    def alternar_tela_cheia(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def keyPressEvent(self, evento: QKeyEvent) -> None:
        tecla = evento.key()
        acoes = {
            Qt.Key.Key_Right: lambda: self.navegar(+1),
            Qt.Key.Key_Left: lambda: self.navegar(-1),
            Qt.Key.Key_PageDown: lambda: self.navegar(+1),
            Qt.Key.Key_PageUp: lambda: self.navegar(-1),
            Qt.Key.Key_Home: lambda: self.exibir(0),
            Qt.Key.Key_End: lambda: self.exibir(self.total - 1),
            Qt.Key.Key_Space: self.alternar_play,
            Qt.Key.Key_M: self.alternar_mudo,
            Qt.Key.Key_F11: self.alternar_tela_cheia,
            Qt.Key.Key_F: self.alternar_tela_cheia,
        }
        if tecla in acoes:
            acoes[tecla]()
            return
        if tecla == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            return
        super().keyPressEvent(evento)

    def _encerrar(self) -> None:
        self._geracao += 1
        self.player.stop()
        self.player.setSource(QUrl())
        self._pool.clear()
        self._pool.waitForDone(3000)

    def closeEvent(self, evento) -> None:
        self._encerrar()
        super().closeEvent(evento)

    def done(self, resultado: int) -> None:  # Esc fecha por aqui (reject), sem closeEvent
        self._encerrar()
        super().done(resultado)
