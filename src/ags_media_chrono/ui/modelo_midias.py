"""Modelo Qt com a lista de mídias da pasta aberta."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QImage

from ags_media_chrono.core.midias import Midia, TipoMidia

PapelMidia = Qt.ItemDataRole.UserRole + 1
PapelMiniatura = Qt.ItemDataRole.UserRole + 2  # QImage | None
PapelDuracao = Qt.ItemDataRole.UserRole + 3  # segundos (float) | None

_Indice = QModelIndex | QPersistentModelIndex


class ModeloMidias(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._midias: list[Midia] = []
        self._linhas: dict[Path, int] = {}
        self._miniaturas: dict[Path, QImage] = {}
        self._duracoes: dict[Path, float] = {}

    def rowCount(self, parent: _Indice = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._midias)

    def data(self, index: _Indice, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        midia = self._midias[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return midia.nome
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(midia.caminho)
        if role == PapelMidia:
            return midia
        if role == PapelMiniatura:
            return self._miniaturas.get(midia.caminho)
        if role == PapelDuracao:
            return self._duracoes.get(midia.caminho)
        return None

    def midia(self, linha: int) -> Midia:
        return self._midias[linha]

    def midias(self) -> list[Midia]:
        return list(self._midias)

    def limpar(self) -> None:
        self.beginResetModel()
        self._midias = []
        self._linhas = {}
        self._miniaturas = {}
        self._duracoes = {}
        self.endResetModel()

    def adicionar(self, midias: list[Midia]) -> None:
        if not midias:
            return
        inicio = len(self._midias)
        self.beginInsertRows(QModelIndex(), inicio, inicio + len(midias) - 1)
        for i, m in enumerate(midias, start=inicio):
            self._linhas[m.caminho] = i
        self._midias.extend(midias)
        self.endInsertRows()

    def definir_miniatura(self, caminho: Path, imagem: QImage) -> None:
        self._atualizar(caminho, self._miniaturas, imagem, PapelMiniatura)

    def definir_duracao(self, caminho: Path, segundos: float) -> None:
        self._atualizar(caminho, self._duracoes, segundos, PapelDuracao)

    def _atualizar(self, caminho: Path, destino: dict, valor, papel: int) -> None:
        linha = self._linhas.get(caminho)
        if linha is None:  # arquivo de uma pasta que já foi fechada
            return
        destino[caminho] = valor
        indice = self.index(linha)
        self.dataChanged.emit(indice, indice, [papel])

    def contagem(self) -> dict[TipoMidia, int]:
        total = {TipoMidia.FOTO: 0, TipoMidia.VIDEO: 0}
        for m in self._midias:
            total[m.tipo] += 1
        return total
