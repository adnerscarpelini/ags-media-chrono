"""Localiza as ferramentas externas (ExifTool, FFmpeg, FFprobe).

Ordem de busca:
1. Variável de ambiente (AGS_EXIFTOOL, AGS_FFMPEG, AGS_FFPROBE)
2. tools/bin/ junto ao executável empacotado (PyInstaller)
3. tools/bin/ na raiz do projeto (baixado por tools/baixar_ferramentas.py)
4. PATH do sistema (ex.: exiftool/ffmpeg instalados via apt no Linux)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

EXE = ".exe" if sys.platform == "win32" else ""

# nome -> caminho relativo dentro de tools/bin/
FERRAMENTAS: dict[str, Path] = {
    "exiftool": Path("exiftool") / f"exiftool{EXE}",
    "ffmpeg": Path("ffmpeg") / f"ffmpeg{EXE}",
    "ffprobe": Path("ffmpeg") / f"ffprobe{EXE}",
}


class FerramentaNaoEncontrada(Exception):
    def __init__(self, nome: str) -> None:
        self.nome = nome
        super().__init__(
            f"{nome} não encontrado. Rode 'python tools/baixar_ferramentas.py' "
            f"ou instale-o no sistema (ou defina a variável AGS_{nome.upper()})."
        )


def pastas_bin_padrao() -> list[Path]:
    pastas = []
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        pastas.append(base / "tools" / "bin")
    # src/ags_media_chrono/core/ferramentas.py -> raiz do projeto
    pastas.append(Path(__file__).resolve().parents[3] / "tools" / "bin")
    return pastas


def localizar(nome: str, *, pastas_bin: list[Path] | None = None, usar_path: bool = True) -> Path:
    if nome not in FERRAMENTAS:
        raise ValueError(f"Ferramenta desconhecida: {nome}")

    if env := os.environ.get(f"AGS_{nome.upper()}"):
        caminho = Path(env)
        if caminho.is_file():
            return caminho

    for pasta in pastas_bin if pastas_bin is not None else pastas_bin_padrao():
        caminho = pasta / FERRAMENTAS[nome]
        if caminho.is_file():
            return caminho

    if usar_path and (encontrado := shutil.which(nome)):
        return Path(encontrado)

    raise FerramentaNaoEncontrada(nome)


def ferramentas_ausentes(**kwargs) -> list[str]:
    ausentes = []
    for nome in FERRAMENTAS:
        try:
            localizar(nome, **kwargs)
        except FerramentaNaoEncontrada:
            ausentes.append(nome)
    return ausentes
