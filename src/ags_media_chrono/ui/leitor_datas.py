"""Leitura das datas dos arquivos em segundo plano (um processo ExifTool próprio)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal

from ags_media_chrono.core.datas import ler_datas
from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada
from ags_media_chrono.ui.threads import emitir

TAMANHO_LOTE = 40  # arquivos por chamada: pequeno o bastante para a tela ir se atualizando


class LeitorDatas(QObject):
    lote = Signal(int, list)  # geração, list[DatasArquivo]
    falhou = Signal(int, str)  # geração, mensagem (ex.: ExifTool ausente)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.geracao = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)  # um ExifTool, comandos em sequência
        self._exiftool: ExifTool | None = None
        self._lock = threading.Lock()
        self._lidos: set[Path] = set()  # acesso com _lock
        self._prioridade = 0

    def nova_geracao(self) -> int:
        self._pool.clear()
        with self._lock:
            self.geracao += 1
            self._lidos.clear()
        return self.geracao

    def ler(self, arquivos: list[Path]) -> None:
        """Enfileira a leitura de todos (prioridade baixa), em lotes."""
        geracao = self.geracao
        for i in range(0, len(arquivos), TAMANHO_LOTE):
            parte = arquivos[i : i + TAMANHO_LOTE]
            self._pool.start(lambda p=parte: self._trabalhar(geracao, p), 0)

    def ler_agora(self, arquivo: Path) -> None:
        """Lê um arquivo antes dos demais (ex.: o que está em foco no painel)."""
        with self._lock:
            if arquivo in self._lidos:
                return
        self._prioridade += 1
        geracao = self.geracao
        self._pool.start(lambda: self._trabalhar(geracao, [arquivo]), self._prioridade)

    def reler(self, arquivos: list[Path]) -> None:
        """Lê de novo (ex.: depois de gravar), mesmo que já tenham sido lidos."""
        with self._lock:
            self._lidos.difference_update(arquivos)
        self._prioridade += 1
        geracao = self.geracao
        self._pool.start(lambda: self._trabalhar(geracao, list(arquivos)), self._prioridade)

    def fechar(self) -> None:
        self._pool.clear()
        self._pool.waitForDone(5000)
        if self._exiftool:
            self._exiftool.fechar()
            self._exiftool = None

    def _trabalhar(self, geracao: int, arquivos: list[Path]) -> None:
        with self._lock:
            if geracao != self.geracao:
                return
            pendentes = [a for a in arquivos if a not in self._lidos]
            self._lidos.update(pendentes)
        if not pendentes:
            return
        try:
            if self._exiftool is None:
                self._exiftool = ExifTool()
            resultados = ler_datas(pendentes, self._exiftool)
        except (FerramentaNaoEncontrada, OSError) as e:
            emitir(self.falhou, geracao, str(e))
            return
        except Exception as e:  # noqa: BLE001 — ex.: ExifTool travou; tenta de novo depois
            with self._lock:
                self._lidos.difference_update(pendentes)
            emitir(self.falhou, geracao, str(e))
            return
        emitir(self.lote, geracao, resultados)
