"""Modelo Qt com a lista de mídias da pasta aberta."""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QImage

from ags_media_chrono.core.datas import DatasArquivo, OpcoesFuso
from ags_media_chrono.core.escolhas import Escolha, EstadoMidia, Status
from ags_media_chrono.core.midias import Midia, TipoMidia

PapelMidia = Qt.ItemDataRole.UserRole + 1
PapelMiniatura = Qt.ItemDataRole.UserRole + 2  # QImage | None
PapelDuracao = Qt.ItemDataRole.UserRole + 3  # segundos (float) | None
PapelEstado = Qt.ItemDataRole.UserRole + 4  # EstadoMidia (datas, escolha, status)
PapelStatus = Qt.ItemDataRole.UserRole + 5  # Status
# Papéis de ordenação: valores simples, comparados pelo próprio Qt (rápido).
PapelOrdemNome = Qt.ItemDataRole.UserRole + 10
PapelOrdemData = Qt.ItemDataRole.UserRole + 11
PapelOrdemTipo = Qt.ItemDataRole.UserRole + 12
PapelOrdemTamanho = Qt.ItemDataRole.UserRole + 13
PapelOrdemEscolhida = Qt.ItemDataRole.UserRole + 14

MAX_MINIATURAS_MEMORIA = 600  # ~320x240x3 bytes cada => ~140 MB no máximo

_Indice = QModelIndex | QPersistentModelIndex
_NUMEROS = re.compile(r"\d+")


def chave_natural(nome: str) -> str:
    """Chave de ordenação "natural": IMG_2 antes de IMG_10, sem diferenciar maiúsculas."""
    return _NUMEROS.sub(lambda m: m.group().zfill(12), nome.casefold())


class ModeloMidias(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._midias: list[Midia] = []
        self._chaves: list[str] = []  # chave_natural do nome, calculada uma vez
        self._linhas: dict[Path, int] = {}
        # LRU: só as miniaturas usadas mais recentemente ficam na memória; as demais são
        # pedidas de novo (vêm rápido do cache em disco) quando voltam a aparecer na tela.
        self._miniaturas: OrderedDict[Path, QImage] = OrderedDict()
        self.max_miniaturas = MAX_MINIATURAS_MEMORIA
        self._duracoes: dict[Path, float] = {}
        self._estados: dict[Path, EstadoMidia] = {}
        self.opcoes_fuso = OpcoesFuso()

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
            imagem = self._miniaturas.get(midia.caminho)
            if imagem is not None:
                self._miniaturas.move_to_end(midia.caminho)
            return imagem
        if role == PapelDuracao:
            return self._duracoes.get(midia.caminho)
        if role == PapelOrdemNome:
            return self._chaves[index.row()]
        if role == PapelOrdemData:
            return midia.modificado
        if role == PapelOrdemTipo:
            return f"{midia.tipo.value}|{midia.caminho.suffix.lower()}|{self._chaves[index.row()]}"
        if role == PapelOrdemTamanho:
            return midia.tamanho
        if role == PapelEstado:
            return self.estado(midia.caminho)
        if role == PapelStatus:
            return self.estado(midia.caminho).status
        if role == PapelOrdemEscolhida:
            # Data escolhida; sem escolha, vai para o fim (por data de modificação).
            escolha = self.estado(midia.caminho).escolha
            return escolha.final.timestamp() if escolha else 1e12 + midia.modificado
        return None

    def midia(self, linha: int) -> Midia:
        return self._midias[linha]

    def midias(self) -> list[Midia]:
        return list(self._midias)

    def limpar(self) -> None:
        self.beginResetModel()
        self._midias = []
        self._chaves = []
        self._linhas = {}
        self._miniaturas = OrderedDict()
        self._duracoes = {}
        self._estados = {}
        self.endResetModel()

    def adicionar(self, midias: list[Midia]) -> None:
        if not midias:
            return
        inicio = len(self._midias)
        self.beginInsertRows(QModelIndex(), inicio, inicio + len(midias) - 1)
        for i, m in enumerate(midias, start=inicio):
            self._linhas[m.caminho] = i
        self._midias.extend(midias)
        self._chaves.extend(chave_natural(m.nome) for m in midias)
        self.endInsertRows()

    def definir_miniatura(self, caminho: Path, imagem: QImage) -> None:
        if not self._atualizar(caminho, self._miniaturas, imagem, PapelMiniatura):
            return
        self._miniaturas.move_to_end(caminho)
        while len(self._miniaturas) > self.max_miniaturas:
            self._miniaturas.popitem(last=False)

    def definir_duracao(self, caminho: Path, segundos: float) -> None:
        self._atualizar(caminho, self._duracoes, segundos, PapelDuracao)

    def _atualizar(self, caminho: Path, destino: dict, valor, papel: int) -> bool:
        linha = self._linhas.get(caminho)
        if linha is None:  # arquivo de uma pasta que já foi fechada
            return False
        destino[caminho] = valor
        indice = self.index(linha)
        self.dataChanged.emit(indice, indice, [papel])
        return True

    # --- datas e escolhas ------------------------------------------------------------------

    def estado(self, caminho: Path) -> EstadoMidia:
        if caminho not in self._estados:
            self._estados[caminho] = EstadoMidia()
        return self._estados[caminho]

    def midia_por_caminho(self, caminho: Path) -> Midia | None:
        linha = self._linhas.get(caminho)
        return self._midias[linha] if linha is not None else None

    def reiniciar_estado(self, caminho: Path) -> None:
        """Esquece datas e escolha (ex.: depois de desfazer); serão lidas de novo."""
        if caminho in self._linhas:
            self._estados[caminho] = EstadoMidia()
            self._estado_alterado(caminho)

    def definir_datas(self, datas: DatasArquivo) -> None:
        if datas.arquivo not in self._linhas:
            return
        self.estado(datas.arquivo).receber_datas(datas, self.opcoes_fuso)
        self._estado_alterado(datas.arquivo)

    def definir_escolha(self, caminho: Path, escolha: Escolha | None) -> None:
        if caminho not in self._linhas:
            return
        self.estado(caminho).escolher(escolha)
        self._estado_alterado(caminho)

    def definir_status(self, caminho: Path, status: Status, mensagem: str = "") -> None:
        if caminho not in self._linhas:
            return
        estado = self.estado(caminho)
        estado.status, estado.mensagem = status, mensagem
        self._estado_alterado(caminho)

    def _estado_alterado(self, caminho: Path) -> None:
        indice = self.index(self._linhas[caminho])
        self.dataChanged.emit(indice, indice, [PapelEstado, PapelStatus, PapelOrdemEscolhida])

    def contagem_status(self) -> dict[Status, int]:
        total = dict.fromkeys(Status, 0)
        for m in self._midias:
            total[self.estado(m.caminho).status] += 1
        return total

    def contagem(self) -> dict[TipoMidia, int]:
        total = {TipoMidia.FOTO: 0, TipoMidia.VIDEO: 0}
        for m in self._midias:
            total[m.tipo] += 1
        return total
