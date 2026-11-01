"""Modelo Qt com a lista de mídias da pasta aberta."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt

from ags_media_chrono.core.midias import Midia, TipoMidia

PapelMidia = Qt.ItemDataRole.UserRole + 1

_Indice = QModelIndex | QPersistentModelIndex


class ModeloMidias(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._midias: list[Midia] = []

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
        return None

    def midia(self, linha: int) -> Midia:
        return self._midias[linha]

    def midias(self) -> list[Midia]:
        return list(self._midias)

    def limpar(self) -> None:
        self.beginResetModel()
        self._midias = []
        self.endResetModel()

    def adicionar(self, midias: list[Midia]) -> None:
        if not midias:
            return
        inicio = len(self._midias)
        self.beginInsertRows(QModelIndex(), inicio, inicio + len(midias) - 1)
        self._midias.extend(midias)
        self.endInsertRows()

    def contagem(self) -> dict[TipoMidia, int]:
        total = {TipoMidia.FOTO: 0, TipoMidia.VIDEO: 0}
        for m in self._midias:
            total[m.tipo] += 1
        return total
