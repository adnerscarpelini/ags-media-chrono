"""Grade de miniaturas (QListView em modo ícone + delegate próprio)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.ui.modelo_midias import PapelDuracao, PapelMidia, PapelMiniatura
from ags_media_chrono.ui.tema import CORES

TAMANHO_PADRAO = 160
TAMANHO_MIN = 64
TAMANHO_MAX = 400
PASSO_ZOOM = 16  # pixels por "clique" da roda do mouse
MARGEM = 6  # espaço interno da célula
ALTURA_TEXTO = 20


def formatar_duracao(segundos: float) -> str:
    total = int(round(segundos))
    h, resto = divmod(total, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class DelegadoMiniatura(QStyledItemDelegate):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tamanho = TAMANHO_PADRAO
        # Chamado ao desenhar um item ainda sem miniatura (só itens visíveis são desenhados).
        self.solicitar_miniatura: Callable[[Midia], None] | None = None
        self._cor = {k: QColor(v) for k, v in CORES.items()}
        self._fonte_rotulo = QFont()
        self._fonte_rotulo.setPixelSize(11)
        self._fonte_rotulo.setBold(True)
        self._fonte_selo = QFont()
        self._fonte_selo.setPixelSize(10)
        self._fonte_selo.setBold(True)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(self.tamanho + 2 * MARGEM, self.tamanho + ALTURA_TEXTO + 2 * MARGEM)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        celula = option.rect.adjusted(1, 1, -1, -1)
        selecionado = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selecionado or hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._cor["painel_alto"] if not selecionado else self._cor["borda"])
            painter.drawRoundedRect(QRectF(celula), 6, 6)

        area = QRect(option.rect.x() + MARGEM, option.rect.y() + MARGEM, self.tamanho, self.tamanho)
        midia = index.data(PapelMidia)
        imagem = index.data(PapelMiniatura)

        if imagem is not None and not imagem.isNull():
            alvo = self._encaixar(imagem.size(), area)
            painter.drawImage(alvo, imagem)
        else:
            alvo = area.adjusted(8, 8, -8, -8)
            self._desenhar_placeholder(painter, alvo, midia.caminho.suffix.lstrip(".").upper())
            if self.solicitar_miniatura:
                self.solicitar_miniatura(midia)

        if selecionado:
            painter.setPen(QPen(self._cor["destaque"], 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(alvo).adjusted(-1, -1, 1, 1))

        if midia.tipo == TipoMidia.VIDEO:
            self._desenhar_selo_video(painter, alvo, index.data(PapelDuracao))

        texto = QRect(area.x(), area.bottom() + 2, area.width(), ALTURA_TEXTO)
        painter.setPen(QColor("white") if selecionado else self._cor["texto"])
        painter.setFont(option.font)
        nome = QFontMetrics(option.font).elidedText(
            midia.nome, Qt.TextElideMode.ElideMiddle, texto.width()
        )
        painter.drawText(texto, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, nome)
        painter.restore()

    @staticmethod
    def _encaixar(tamanho: QSize, area: QRect) -> QRect:
        """Redimensiona mantendo a proporção e centraliza na área."""
        escalado = tamanho.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
        x = area.x() + (area.width() - escalado.width()) // 2
        y = area.y() + (area.height() - escalado.height()) // 2
        return QRect(x, y, escalado.width(), escalado.height())

    def _desenhar_placeholder(self, painter: QPainter, alvo: QRect, extensao: str) -> None:
        painter.setPen(self._cor["borda_forte"])
        painter.setBrush(self._cor["painel"])
        painter.drawRoundedRect(QRectF(alvo), 4, 4)
        painter.setPen(self._cor["texto_desativado"])
        painter.setFont(self._fonte_rotulo)
        painter.drawText(alvo, Qt.AlignmentFlag.AlignCenter, extensao)

    def _desenhar_selo_video(self, painter: QPainter, alvo: QRect, duracao: float | None) -> None:
        texto = formatar_duracao(duracao) if duracao else ""
        fm = QFontMetrics(self._fonte_selo)
        largura = 18 + (fm.horizontalAdvance(texto) + 6 if texto else 0)
        selo = QRectF(alvo.left() + 5, alvo.bottom() - 21, largura, 16)

        caminho = QPainterPath()
        caminho.addRoundedRect(selo, 3, 3)
        painter.fillPath(caminho, QColor(0, 0, 0, 170))

        cx, cy = selo.left() + 9, selo.center().y()
        triangulo = QPolygonF(
            [QPointF(cx - 3, cy - 4), QPointF(cx - 3, cy + 4), QPointF(cx + 4, cy)]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("white"))
        painter.drawPolygon(triangulo)

        if texto:
            painter.setPen(QColor("white"))
            painter.setFont(self._fonte_selo)
            area_texto = selo.adjusted(16, 0, -4, 0)
            painter.drawText(area_texto, Qt.AlignmentFlag.AlignVCenter, texto)


class VisaoGaleria(QListView):
    tamanho_alterado = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.delegado = DelegadoMiniatura(self)
        self.setItemDelegate(self.delegado)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        # Com itens uniformes o layout é barato; em uma passada só dá para reposicionar
        # a rolagem logo após o zoom.
        self.setLayoutMode(QListView.LayoutMode.SinglePass)
        self.setSpacing(4)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setObjectName("grade")

    @property
    def tamanho(self) -> int:
        return self.delegado.tamanho

    def definir_tamanho(self, pixels: int) -> None:
        pixels = max(TAMANHO_MIN, min(TAMANHO_MAX, pixels))
        if pixels == self.delegado.tamanho:
            return
        ancora = self._item_ancora()
        self.delegado.tamanho = pixels
        # Recalcula o layout agora (e não no próximo ciclo) para reposicionar a rolagem.
        self.doItemsLayout()
        if ancora.isValid():
            self.scrollTo(ancora, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.tamanho_alterado.emit(pixels)

    def _item_ancora(self) -> QModelIndex:
        """Item que deve continuar visível após o zoom: o atual, se estiver na tela, senão o
        primeiro visível."""
        atual = self.currentIndex()
        if atual.isValid() and self.viewport().rect().intersects(self.visualRect(atual)):
            return atual
        return self.indexAt(QPoint(self.spacing() + MARGEM, self.spacing() + MARGEM))

    def wheelEvent(self, evento: QWheelEvent) -> None:
        if evento.modifiers() & Qt.KeyboardModifier.ControlModifier:
            passos = evento.angleDelta().y() / 120
            if passos:
                self.definir_tamanho(round(self.tamanho + passos * PASSO_ZOOM))
            evento.accept()
            return
        super().wheelEvent(evento)
