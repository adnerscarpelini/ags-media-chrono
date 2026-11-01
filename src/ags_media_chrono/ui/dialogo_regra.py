"""Diálogo "Escolher data por regra" (issue #15)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ags_media_chrono.core.datas import OpcoesFuso
from ags_media_chrono.core.escolhas import EstadoMidia
from ags_media_chrono.core.regras import Alvo, Criterio, Regra, ResultadoRegra, simular_regra
from ags_media_chrono.ui.config import configuracoes

CHAVE_PREDEFINICOES = "regras/predefinicoes"
CHAVE_ULTIMA = "regras/ultima"
PREDEFINICOES_PADRAO = {
    "Captura → nome → mais antiga": Regra(),
    "WhatsApp: nome → modificação do arquivo": Regra(
        [Criterio.CAPTURA, Criterio.NOME, Criterio.MODIFICACAO_ARQUIVO]
    ),
    "Mais antiga de todas": Regra([Criterio.MAIS_ANTIGA]),
}


def carregar_predefinicoes(config: QSettings) -> dict[str, Regra]:
    try:
        salvas = json.loads(config.value(CHAVE_PREDEFINICOES, "{}"))
    except (TypeError, ValueError):
        salvas = {}
    return {**PREDEFINICOES_PADRAO, **{n: Regra.de_dict(d) for n, d in salvas.items()}}


def salvar_predefinicao(config: QSettings, nome: str, regra: Regra | None) -> None:
    try:
        salvas = json.loads(config.value(CHAVE_PREDEFINICOES, "{}"))
    except (TypeError, ValueError):
        salvas = {}
    if regra is None:
        salvas.pop(nome, None)
    else:
        salvas[nome] = regra.para_dict()
    config.setValue(CHAVE_PREDEFINICOES, json.dumps(salvas, ensure_ascii=False))


class DialogoRegra(QDialog):
    def __init__(
        self,
        estados: dict[Path, EstadoMidia],
        opcoes: OpcoesFuso | None = None,
        config: QSettings | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Escolher data por regra")
        self.setMinimumWidth(520)
        self.estados = estados
        self.opcoes = opcoes
        self.config = config or configuracoes()
        self.resultado: ResultadoRegra | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        intro = QLabel(
            f"Aplicar em <b>{len(estados)}</b> arquivo(s). Para cada um, é usado o "
            "<b>primeiro</b> critério marcado que encontrar uma data. Arraste ou use as setas "
            "para mudar a ordem."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        linha_pred = QHBoxLayout()
        linha_pred.addWidget(QLabel("Predefinição"))
        self.combo_predefinicao = QComboBox()
        self.combo_predefinicao.activated.connect(self._carregar_predefinicao)
        linha_pred.addWidget(self.combo_predefinicao, 1)
        salvar = QPushButton("Salvar…")
        salvar.clicked.connect(self._salvar_predefinicao)
        excluir = QPushButton("Excluir")
        excluir.clicked.connect(self._excluir_predefinicao)
        linha_pred.addWidget(salvar)
        linha_pred.addWidget(excluir)
        layout.addLayout(linha_pred)

        linha_lista = QHBoxLayout()
        self.lista = QListWidget()
        self.lista.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lista.itemChanged.connect(self._atualizar_previa)
        self.lista.model().rowsMoved.connect(self._atualizar_previa)
        linha_lista.addWidget(self.lista, 1)
        setas = QVBoxLayout()
        for texto, passo in (("▲", -1), ("▼", +1)):
            botao = QPushButton(texto)
            botao.setFixedWidth(36)
            botao.clicked.connect(lambda _=False, p=passo: self._mover(p))
            setas.addWidget(botao)
        setas.addStretch(1)
        linha_lista.addLayout(setas)
        layout.addLayout(linha_lista)

        linha_alvo = QHBoxLayout()
        linha_alvo.addWidget(QLabel("Quais arquivos"))
        self.combo_alvo = QComboBox()
        for alvo in Alvo:
            self.combo_alvo.addItem(alvo.rotulo, alvo)
        self.combo_alvo.currentIndexChanged.connect(self._atualizar_previa)
        linha_alvo.addWidget(self.combo_alvo, 1)
        layout.addLayout(linha_alvo)

        self.previa = QLabel()
        self.previa.setObjectName("resumoEscolha")
        self.previa.setWordWrap(True)
        layout.addWidget(self.previa)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar regra")
        botoes.accepted.connect(self._aceitar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

        self._recarregar_predefinicoes()
        ultima = self.config.value(CHAVE_ULTIMA)
        try:
            regra = Regra.de_dict(json.loads(ultima)) if ultima else Regra()
        except (TypeError, ValueError):
            regra = Regra()
        self.definir_regra(regra)

    # --- regra <-> tela -------------------------------------------------------------------

    def definir_regra(self, regra: Regra) -> None:
        self.lista.blockSignals(True)
        self.lista.clear()
        ordem = regra.criterios + [c for c in Criterio if c not in regra.criterios]
        for criterio in ordem:
            item = QListWidgetItem(criterio.rotulo)
            item.setData(Qt.ItemDataRole.UserRole, criterio)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            marcado = criterio in regra.criterios
            item.setCheckState(Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked)
            self.lista.addItem(item)
        self.lista.blockSignals(False)
        self.combo_alvo.setCurrentIndex(list(Alvo).index(regra.alvo))
        self._atualizar_previa()

    def regra(self) -> Regra:
        criterios = []
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                criterios.append(Criterio(item.data(Qt.ItemDataRole.UserRole)))
        # O Qt devolve enums guardados em widgets como str simples: converte de volta.
        return Regra(criterios, Alvo(self.combo_alvo.currentData()))

    def _mover(self, passo: int) -> None:
        linha = self.lista.currentRow()
        destino = linha + passo
        if linha < 0 or not 0 <= destino < self.lista.count():
            return
        item = self.lista.takeItem(linha)
        self.lista.insertItem(destino, item)
        self.lista.setCurrentRow(destino)
        self._atualizar_previa()

    def _atualizar_previa(self, *_args) -> None:
        r = simular_regra(self.estados, self.regra(), self.opcoes)
        partes = [f"<b>{len(r.escolhas)}</b> recebem data"]
        if r.sem_data:
            partes.append(f"<b>{len(r.sem_data)}</b> continuam sem data")
        if r.ignorados:
            partes.append(f"{r.ignorados} mantidos (fora do critério de arquivos)")
        if r.nao_lidos:
            partes.append(f"{r.nao_lidos} ainda sendo lidos (ignorados)")
        self.previa.setText("Resultado: " + ", ".join(partes) + ".")

    # --- predefinições --------------------------------------------------------------------

    def _recarregar_predefinicoes(self) -> None:
        self.combo_predefinicao.clear()
        self._predefinicoes = carregar_predefinicoes(self.config)
        self.combo_predefinicao.addItem("—", None)
        for nome in self._predefinicoes:
            self.combo_predefinicao.addItem(nome, nome)

    def _carregar_predefinicao(self, indice: int) -> None:
        nome = self.combo_predefinicao.itemData(indice)
        if nome:
            self.definir_regra(self._predefinicoes[nome])

    def _salvar_predefinicao(self) -> None:
        nome, ok = QInputDialog.getText(self, "Salvar predefinição", "Nome da predefinição:")
        if ok and nome.strip():
            salvar_predefinicao(self.config, nome.strip(), self.regra())
            self._recarregar_predefinicoes()
            self.combo_predefinicao.setCurrentIndex(self.combo_predefinicao.findData(nome.strip()))

    def _excluir_predefinicao(self) -> None:
        nome = self.combo_predefinicao.currentData()
        if nome and nome not in PREDEFINICOES_PADRAO:
            salvar_predefinicao(self.config, nome, None)
            self._recarregar_predefinicoes()

    def _aceitar(self) -> None:
        regra = self.regra()
        self.config.setValue(CHAVE_ULTIMA, json.dumps(regra.para_dict()))
        self.resultado = simular_regra(self.estados, regra, self.opcoes)
        self.accept()
