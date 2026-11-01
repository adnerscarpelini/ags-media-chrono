"""Interface da gravação de datas: opções, progresso, relatório e histórico (issues #18–#22)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.gravacao import (
    SUPORTA_DATA_CRIACAO,
    GrupoCampos,
    OpcoesGravacao,
    aplicar_lote,
    desfazer_operacao,
    grupos_padrao,
)
from ags_media_chrono.core.historico import Operacao, TipoOperacao, listar_operacoes
from ags_media_chrono.core.midias import Midia
from ags_media_chrono.ui.config import configuracoes
from ags_media_chrono.ui.threads import emitir

CHAVE_OPCOES = "gravacao/opcoes"


# --- opções ---------------------------------------------------------------------------------


class DialogoAplicar(QDialog):
    """Confirmação antes de gravar: quais campos, backup."""

    def __init__(
        self,
        quantidade: int,
        quicktime_utc: bool = True,
        renomear_depois: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aplicar datas")
        self.setMinimumWidth(500)
        self.config = configuracoes()
        salvas = self._opcoes_salvas()

        layout = QVBoxLayout(self)
        titulo = QLabel(
            f"Gravar a data escolhida em <b>{quantidade}</b> arquivo(s).<br>Campos a atualizar:"
        )
        layout.addWidget(titulo)
        self.caixas: dict[GrupoCampos, QCheckBox] = {}
        for grupo in GrupoCampos:
            caixa = QCheckBox(grupo.rotulo)
            caixa.setChecked(grupo in salvas.grupos)
            if grupo == GrupoCampos.ARQUIVO_CRIACAO and not SUPORTA_DATA_CRIACAO:
                caixa.setChecked(False)
                caixa.setEnabled(False)
                caixa.setToolTip(
                    "No Linux a maioria dos sistemas de arquivos não permite alterar a data "
                    "de criação. Os metadados e a data de modificação são alterados normalmente."
                )
            self.caixas[grupo] = caixa
            layout.addWidget(caixa)
        if not SUPORTA_DATA_CRIACAO:
            aviso = QLabel("Neste sistema a data de criação do arquivo não pode ser alterada.")
            aviso.setObjectName("vazio")
            layout.addWidget(aviso)

        self.caixa_utc = QCheckBox("Gravar datas QuickTime dos vídeos em UTC (recomendado)")
        self.caixa_utc.setChecked(quicktime_utc)
        self.caixa_utc.setToolTip(
            "Padrão da especificação e do iPhone. Desmarque só se seus aparelhos gravam "
            "o horário local nesses campos."
        )
        layout.addWidget(self.caixa_utc)

        self.caixa_backup = QCheckBox("Guardar cópia dos originais antes de gravar")
        self.caixa_backup.setChecked(salvas.backup)
        self.caixa_backup.setToolTip(
            "Cópias ficam em '_backup_ags-media-chrono' dentro da pasta de cada arquivo.\n"
            "Mesmo sem cópia, é possível desfazer pelo histórico (Editar > Desfazer)."
        )
        layout.addWidget(self.caixa_backup)

        self.caixa_renomear = QCheckBox("Renomear os arquivos em seguida (com as datas novas)")
        self.caixa_renomear.setChecked(renomear_depois)
        layout.addWidget(self.caixa_renomear)

        nota = QLabel(
            "Todas as alterações ficam registradas e podem ser desfeitas em "
            "<b>Editar › Desfazer última aplicação</b>."
        )
        nota.setObjectName("vazio")
        nota.setWordWrap(True)
        layout.addWidget(nota)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Gravar")
        botoes.accepted.connect(self._aceitar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _opcoes_salvas(self) -> OpcoesGravacao:
        try:
            dados = json.loads(self.config.value(CHAVE_OPCOES, "{}"))
            grupos = frozenset(GrupoCampos(g) for g in dados["grupos"]) & grupos_padrao()
            return OpcoesGravacao(grupos=grupos, backup=bool(dados.get("backup", False)))
        except (TypeError, ValueError, KeyError):
            return OpcoesGravacao()

    def opcoes(self) -> OpcoesGravacao:
        grupos = frozenset(g for g, c in self.caixas.items() if c.isChecked() and c.isEnabled())
        return OpcoesGravacao(
            grupos=grupos, backup=self.caixa_backup.isChecked(),
            quicktime_utc=self.caixa_utc.isChecked(),
        )  # fmt: skip

    def _aceitar(self) -> None:
        opcoes = self.opcoes()
        if not opcoes.grupos:
            QMessageBox.warning(self, "Aplicar datas", "Marque pelo menos um grupo de campos.")
            return
        dados = {"grupos": [g.value for g in opcoes.grupos], "backup": opcoes.backup}
        self.config.setValue(CHAVE_OPCOES, json.dumps(dados))
        self.accept()


# --- trabalho em segundo plano --------------------------------------------------------------


class TrabalhoGravacao(QObject):
    """Executa gravação ou desfazer numa thread, com seu próprio ExifTool."""

    progresso = Signal(int, int, str)  # atual, total, nome do arquivo
    terminado = Signal(object, bool)  # Operacao (ou lista de resultados, no desfazer), cancelado

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._cancelar = threading.Event()

    def cancelar(self) -> None:
        self._cancelar.set()

    def aguardar(self, ms: int = -1) -> bool:
        return self._pool.waitForDone(ms)

    def _rodar(self, funcao: Callable[[ExifTool], object]) -> None:
        self._cancelar.clear()

        def trabalho() -> None:
            resultado: object = None
            try:
                with ExifTool() as et:
                    resultado = funcao(et)
            except Exception as e:  # noqa: BLE001 — ex.: ExifTool ausente
                resultado = e
            emitir(self.terminado, resultado, self._cancelar.is_set())

        self._pool.start(trabalho)

    def _avisar(self, atual: int, total: int, arquivo: Path) -> None:
        emitir(self.progresso, atual, total, arquivo.name)

    def gravar(self, itens: list[tuple[Midia, datetime]], opcoes: OpcoesGravacao) -> None:
        self._rodar(
            lambda et: aplicar_lote(
                et, itens, opcoes, progresso=self._avisar, cancelado=self._cancelar.is_set
            )
        )

    def desfazer(self, operacao: Operacao) -> None:
        self._rodar(lambda et: desfazer_operacao(et, operacao, progresso=self._avisar))


def dialogo_progresso(titulo: str, total: int, parent: QWidget) -> QProgressDialog:
    progresso = QProgressDialog(titulo, "Cancelar", 0, total, parent)
    progresso.setWindowTitle(titulo)
    progresso.setWindowModality(Qt.WindowModality.WindowModal)
    progresso.setMinimumDuration(300)
    progresso.setAutoClose(False)
    progresso.setAutoReset(False)
    progresso.setMinimumWidth(420)
    return progresso


# --- relatório e histórico ------------------------------------------------------------------


class DialogoRelatorio(QDialog):
    """Resultado por arquivo; erros e avisos primeiro."""

    def __init__(self, titulo: str, entradas: list[dict], cancelado: bool, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        ok = sum(1 for e in entradas if e.get("ok"))
        erros = len(entradas) - ok
        avisos = sum(1 for e in entradas if e.get("ok") and e.get("mensagem"))
        partes = [f"<b>{ok}</b> arquivo(s) gravado(s)"]
        if erros:
            partes.append(f"<b style='color:#e05a5a'>{erros} com erro</b>")
        if avisos:
            partes.append(f"{avisos} com aviso")
        if cancelado:
            partes.append("operação cancelada antes do fim")
        resumo = QLabel(", ".join(partes) + ".")
        resumo.setWordWrap(True)
        layout.addWidget(resumo)

        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(["Arquivo", "Resultado", "Detalhe"])
        self.lista.setRootIsDecorated(False)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        cabecalho = self.lista.header()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for e in sorted(entradas, key=lambda e: (e.get("ok"), not e.get("mensagem"))):
            situacao = "Erro" if not e.get("ok") else ("Aviso" if e.get("mensagem") else "OK")
            item = QTreeWidgetItem([Path(e["arquivo"]).name, situacao, e.get("mensagem", "")])
            item.setToolTip(0, e["arquivo"])
            item.setToolTip(2, e.get("mensagem", ""))
            self.lista.addTopLevelItem(item)
        layout.addWidget(self.lista)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        botoes.rejected.connect(self.reject)
        botoes.accepted.connect(self.accept)
        layout.addWidget(botoes)


def descrever_operacao(op: Operacao) -> str:
    quando = datetime.fromisoformat(op.quando).strftime("%d/%m/%Y %H:%M:%S")
    tipo = "Datas aplicadas" if op.tipo == TipoOperacao.DATAS else "Arquivos renomeados"
    pastas = {str(Path(e["arquivo"] if "arquivo" in e else e.get("de", "")).parent)
              for e in op.entradas}  # fmt: skip
    pasta = next(iter(pastas)) if len(pastas) == 1 else f"{len(pastas)} pastas"
    estado = " (desfeita)" if op.desfeita else ""
    return f"{quando} — {tipo}: {op.quantidade_ok} arquivo(s) — {pasta}{estado}"


class DialogoHistorico(QDialog):
    """Lista as operações salvas; permite desfazer a selecionada."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Histórico de alterações")
        self.resize(760, 420)
        self.operacao_escolhida: Operacao | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Escolha uma operação para desfazer:"))
        self.lista = QTreeWidget()
        self.lista.setHeaderHidden(True)
        self.lista.setRootIsDecorated(False)
        self.operacoes = listar_operacoes()
        for op in self.operacoes:
            item = QTreeWidgetItem([descrever_operacao(op)])
            item.setData(0, Qt.ItemDataRole.UserRole, op.id)
            if op.desfeita:
                item.setDisabled(True)
            self.lista.addTopLevelItem(item)
        if not self.operacoes:
            self.lista.addTopLevelItem(QTreeWidgetItem(["Nenhuma alteração registrada ainda."]))
        layout.addWidget(self.lista)
        self.botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close
        )
        self.botao_desfazer = self.botoes.button(QDialogButtonBox.StandardButton.Ok)
        self.botao_desfazer.setText("Desfazer selecionada")
        self.botao_desfazer.setEnabled(False)
        self.lista.currentItemChanged.connect(self._ao_selecionar)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        layout.addWidget(self.botoes)

    def _ao_selecionar(self, item: QTreeWidgetItem | None, _anterior=None) -> None:
        id_ = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.operacao_escolhida = next((o for o in self.operacoes if o.id == id_), None)
        self.botao_desfazer.setEnabled(
            self.operacao_escolhida is not None and not self.operacao_escolhida.desfeita
        )
