"""Descoberta de fotos e vídeos em uma pasta."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

EXTENSOES_FOTO = frozenset(
    {
        ".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp",
        # RAW
        ".nef", ".nrw", ".dng", ".cr2", ".cr3", ".arw", ".raf", ".orf", ".rw2",
    }
)  # fmt: skip
EXTENSOES_VIDEO = frozenset(
    {".mov", ".mp4", ".m4v", ".3gp", ".avi", ".mkv", ".mts", ".m2ts", ".wmv", ".webm"}
)


class TipoMidia(StrEnum):
    FOTO = "foto"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class Midia:
    caminho: Path
    tipo: TipoMidia
    tamanho: int
    modificado: float  # timestamp (mtime) do sistema de arquivos

    @property
    def nome(self) -> str:
        return self.caminho.name


def tipo_por_extensao(nome: str) -> TipoMidia | None:
    ext = os.path.splitext(nome)[1].lower()
    if ext in EXTENSOES_FOTO:
        return TipoMidia.FOTO
    if ext in EXTENSOES_VIDEO:
        return TipoMidia.VIDEO
    return None


def _oculto(nome: str) -> bool:
    # Inclui os arquivos "._IMG_0001.JPG" que o macOS cria em pendrives/HDs externos.
    return nome.startswith(".")


def listar_midias(
    pasta: str | Path,
    *,
    subpastas: bool = False,
    cancelado: Callable[[], bool] | None = None,
) -> Iterator[Midia]:
    """Percorre a pasta em ordem alfabética (arquivos primeiro, depois subpastas).

    Pastas sem permissão de leitura são ignoradas. Atalhos/links para pastas não são seguidos,
    evitando ciclos.
    """
    try:
        entradas = sorted(os.scandir(pasta), key=lambda e: e.name.casefold())
    except OSError:
        return

    filhas = []
    for entrada in entradas:
        if cancelado and cancelado():
            return
        if _oculto(entrada.name):
            continue
        try:
            if entrada.is_dir(follow_symlinks=False):
                filhas.append(entrada.path)
                continue
            tipo = tipo_por_extensao(entrada.name)
            if tipo is None or not entrada.is_file():
                continue
            st = entrada.stat()
        except OSError:
            continue
        yield Midia(Path(entrada.path), tipo, st.st_size, st.st_mtime)

    if subpastas:
        for filha in filhas:
            yield from listar_midias(filha, subpastas=True, cancelado=cancelado)
