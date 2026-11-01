"""Ordenação e filtros da galeria (proxy entre ModeloMidias e a grade)."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Qt

from ags_media_chrono.core.escolhas import Status
from ags_media_chrono.core.midias import Midia, TipoMidia
from ags_media_chrono.ui.modelo_midias import (
    PapelOrdemData,
    PapelOrdemEscolhida,
    PapelOrdemNome,
    PapelOrdemTamanho,
    PapelOrdemTipo,
    PapelStatus,
)


class Ordenacao(Enum):
    # (rótulo, papel do modelo usado na comparação)
    NOME = ("Nome", PapelOrdemNome)
    DATA_ESCOLHIDA = ("Data escolhida", PapelOrdemEscolhida)
    DATA_MODIFICACAO = ("Data de modificação", PapelOrdemData)
    TIPO = ("Tipo", PapelOrdemTipo)
    TAMANHO = ("Tamanho", PapelOrdemTamanho)

    @property
    def rotulo(self) -> str:
        return self.value[0]

    @property
    def papel(self) -> int:
        return self.value[1]


class ProxyGaleria(QSortFilterProxyModel):
    """Filtros combináveis (tipo + texto no nome) e ordenação.

    Novos filtros (ex.: status da data, issue #17) entram em `_aceita`.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tipo: TipoMidia | None = None
        self.status: Status | None = None
        self.texto = ""
        self.ordenacao = Ordenacao.NOME
        self.crescente = True
        self.setDynamicSortFilter(True)
        # O filtro em si é feito em filterAcceptsRow; o filterRole diz ao Qt quais mudanças
        # de dados exigem refiltrar a linha (mudança de status com filtro de status ativo).
        self.setFilterRole(PapelStatus)
        self.setSortRole(Ordenacao.NOME.papel)
        self.sort(0, Qt.SortOrder.AscendingOrder)

    def definir_tipo(self, tipo: TipoMidia | None) -> None:
        if tipo != self.tipo:
            self.beginFilterChange()
            self.tipo = tipo
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def definir_status(self, status: Status | None) -> None:
        if status != self.status:
            self.beginFilterChange()
            self.status = status
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def definir_texto(self, texto: str) -> None:
        texto = texto.strip().casefold()
        if texto != self.texto:
            self.beginFilterChange()
            self.texto = texto
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def ordenar(self, ordenacao: Ordenacao, crescente: bool = True) -> None:
        self.ordenacao = ordenacao
        self.crescente = crescente
        self.setSortRole(ordenacao.papel)
        ordem = Qt.SortOrder.AscendingOrder if crescente else Qt.SortOrder.DescendingOrder
        self.sort(0, ordem)

    @property
    def filtrando(self) -> bool:
        return self.tipo is not None or self.status is not None or bool(self.texto)

    def filterAcceptsRow(self, linha: int, pai: QModelIndex | QPersistentModelIndex) -> bool:
        modelo = self.sourceModel()
        midia = modelo.midia(linha)
        if self.status is not None and modelo.estado(midia.caminho).status != self.status:
            return False
        return self._aceita(midia)

    def _aceita(self, midia: Midia) -> bool:
        if self.tipo is not None and midia.tipo != self.tipo:
            return False
        if self.texto and self.texto not in midia.nome.casefold():
            return False
        return True
