"""Geração de miniaturas em segundo plano para a galeria.

- Pedidos da tela (itens visíveis) têm prioridade crescente: o último pedido é atendido
  primeiro, então rolar rápido não deixa a tela esperando itens que já saíram de vista.
- Depois que a pasta carrega, todas as mídias entram na fila com prioridade baixa
  (pré-carregamento), para que a próxima abertura use o cache.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThreadPool, Signal
from PySide6.QtGui import QImage

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada
from ags_media_chrono.core.midias import Midia
from ags_media_chrono.core.miniaturas import EXTENSOES_RAW, CacheMiniaturas, gerar_miniatura
from ags_media_chrono.ui.threads import emitir

PRIORIDADE_FUNDO = 0
NIVEL_FUNDO, NIVEL_TELA = 0, 1


class GeradorMiniaturas(QObject):
    pronta = Signal(int, object, QImage, object)  # geração, Path, imagem, duração|None
    falhou = Signal(int, object, str)  # geração, Path, mensagem

    def __init__(self, parent: QObject | None = None, cache: CacheMiniaturas | None = None):
        super().__init__(parent)
        self.cache = cache or CacheMiniaturas()
        self.geracao = 0
        self.estatisticas = {"cache": 0, "geradas": 0, "falhas": 0}

        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(2, min(6, (os.cpu_count() or 4) // 2)))
        self._prioridade = 0
        # Estado da geração atual; acessado só pela thread da interface.
        self._pendentes: dict[Path, int] = {}
        self._falhas: set[Path] = set()
        self._concluidos: set[Path] = set()
        # Mídias que algum trabalho já começou a processar nesta geração (acesso com _lock).
        # Evita processar duas vezes quando a mesma mídia está na fila de fundo e na da tela.
        self._iniciados: set[Path] = set()
        self._lock = threading.Lock()
        self._exiftool: ExifTool | None = None
        self._lock_exiftool = threading.Lock()

        self.pronta.connect(self._finalizar)
        self.falhou.connect(self._registrar_falha)

    # --- API usada pela interface ----------------------------------------------------------

    def nova_geracao(self) -> int:
        """Descarta tudo o que está na fila (troca de pasta)."""
        self._pool.clear()
        with self._lock:
            self.geracao += 1
            self._iniciados.clear()
        self._pendentes.clear()
        self._falhas.clear()
        self._concluidos.clear()
        self._prioridade = 0
        return self.geracao

    def solicitar(self, midia: Midia) -> None:
        """Pedido da tela: alta prioridade (o mais recente primeiro)."""
        self._enfileirar(midia, NIVEL_TELA)

    def pre_carregar(self, midias: list[Midia]) -> None:
        for midia in midias:
            self._enfileirar(midia, NIVEL_FUNDO)

    def fechar(self) -> None:
        self._pool.clear()
        self._pool.waitForDone(5000)
        with self._lock_exiftool:
            if self._exiftool:
                self._exiftool.fechar()
                self._exiftool = None

    # --- interno ---------------------------------------------------------------------------

    def _enfileirar(self, midia: Midia, nivel: int) -> None:
        caminho = midia.caminho
        if caminho in self._falhas or self._pendentes.get(caminho, -1) >= nivel:
            return
        self._pendentes[caminho] = nivel
        if nivel == NIVEL_TELA:
            self._prioridade += 1
            prioridade = self._prioridade
        else:
            prioridade = PRIORIDADE_FUNDO
        # Já concluída antes: a tela pediu de novo porque o modelo descartou a imagem da
        # memória (LRU). Nesse caso o trabalho precisa rodar mesmo já tendo sido iniciado.
        repetir = caminho in self._concluidos
        geracao = self.geracao
        self._pool.start(lambda: self._trabalhar(geracao, midia, repetir), prioridade)

    def obter_exiftool(self) -> ExifTool | None:
        """ExifTool compartilhado (criado sob demanda); None se não estiver instalado."""
        with self._lock_exiftool:
            if self._exiftool is None:
                try:
                    self._exiftool = ExifTool()
                except FerramentaNaoEncontrada:
                    return None
            return self._exiftool

    def _contar(self, chave: str) -> None:
        with self._lock:
            self.estatisticas[chave] += 1

    def _trabalhar(self, geracao: int, midia: Midia, repetir: bool) -> None:
        with self._lock:
            if geracao != self.geracao or (midia.caminho in self._iniciados and not repetir):
                return
            self._iniciados.add(midia.caminho)
        try:
            miniatura = self.cache.obter(midia)
            if miniatura is not None:
                self._contar("cache")
            else:
                raw = midia.caminho.suffix.lower() in EXTENSOES_RAW
                exiftool = self.obter_exiftool() if raw else None
                miniatura = gerar_miniatura(midia, exiftool)
                self.cache.salvar(midia, miniatura)
                self._contar("geradas")
            imagem = QImage.fromData(miniatura.jpeg)
            if imagem.isNull():
                raise ValueError("miniatura inválida")
            imagem = imagem.convertToFormat(QImage.Format.Format_RGB888)  # 3 bytes/pixel
            emitir(self.pronta, geracao, midia.caminho, imagem, miniatura.duracao)
        except Exception as e:  # noqa: BLE001 — qualquer arquivo problemático vira placeholder
            self._contar("falhas")
            emitir(self.falhou, geracao, midia.caminho, str(e))

    def _finalizar(self, geracao: int, caminho: Path, *_args) -> None:
        if geracao == self.geracao:
            self._pendentes.pop(caminho, None)
            self._concluidos.add(caminho)

    def _registrar_falha(self, geracao: int, caminho: Path, _mensagem: str) -> None:
        if geracao == self.geracao:
            self._pendentes.pop(caminho, None)
            self._falhas.add(caminho)
