"""Leitura da pasta em segundo plano, entregando os arquivos em lotes para a interface."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal

from ags_media_chrono.core.midias import Midia, listar_midias
from ags_media_chrono.ui.threads import emitir

INTERVALO_LOTE = 0.1  # segundos entre lotes enviados à interface


class CarregadorPasta(QObject):
    """Cada carregamento recebe um número de geração; lotes de gerações antigas são ignorados.

    Sinais são emitidos da thread de trabalho e entregues na thread da interface (conexão
    enfileirada automática do Qt).
    """

    lote = Signal(int, list)  # geração, list[Midia]
    concluido = Signal(int, int)  # geração, total

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.geracao = 0
        self._cancelar = threading.Event()
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    def carregar(self, pasta: Path, subpastas: bool) -> int:
        self.cancelar()
        self.geracao += 1
        self._cancelar = cancelar = threading.Event()
        geracao = self.geracao
        self._pool.start(lambda: self._trabalhar(geracao, pasta, subpastas, cancelar))
        return geracao

    def cancelar(self) -> None:
        self._cancelar.set()

    def aguardar(self, ms: int = -1) -> bool:
        return self._pool.waitForDone(ms)

    def _trabalhar(
        self, geracao: int, pasta: Path, subpastas: bool, cancelar: threading.Event
    ) -> None:
        buffer: list[Midia] = []
        total = 0
        ultimo_envio = time.monotonic()
        for midia in listar_midias(pasta, subpastas=subpastas, cancelado=cancelar.is_set):
            buffer.append(midia)
            agora = time.monotonic()
            if agora - ultimo_envio >= INTERVALO_LOTE:
                total += len(buffer)
                emitir(self.lote, geracao, buffer)
                buffer = []
                ultimo_envio = agora
        if cancelar.is_set():
            return
        if buffer:
            total += len(buffer)
            emitir(self.lote, geracao, buffer)
        emitir(self.concluido, geracao, total)
