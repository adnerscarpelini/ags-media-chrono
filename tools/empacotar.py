"""Gera o pacote distribuível do app (Windows: .zip; Linux: .tar.gz e, se possível, AppImage).

Uso (com o ambiente do projeto ativado e `pip install -e ".[dev]"`):
    python tools/empacotar.py
    python tools/empacotar.py --sem-appimage

Passos: baixa ExifTool/FFmpeg (se faltarem), roda o PyInstaller com
empacotamento/ags-media-chrono.spec, testa o executável (--verificar) e compacta em dist/.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIST = RAIZ / "dist"
NOME = "ags-media-chrono"
APPIMAGETOOL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)


def versao() -> str:
    sys.path.insert(0, str(RAIZ / "src"))
    from ags_media_chrono import __version__

    return __version__


def rodar(*args: str, **kwargs) -> None:
    print("$", " ".join(args), flush=True)
    subprocess.run(args, check=True, **kwargs)


def pyinstaller() -> Path:
    rodar(sys.executable, str(RAIZ / "tools" / "baixar_ferramentas.py"))
    rodar(
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", str(DIST), "--workpath", str(RAIZ / "build"),
        str(RAIZ / "empacotamento" / f"{NOME}.spec"),
    )  # fmt: skip
    return DIST / NOME


def verificar(pasta: Path) -> None:
    executavel = pasta / (f"{NOME}.exe" if sys.platform == "win32" else NOME)
    with tempfile.TemporaryDirectory() as tmp:
        relatorio = Path(tmp) / "verificacao.txt"
        ambiente = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        resultado = subprocess.run(
            [str(executavel), "--verificar", str(relatorio)], env=ambiente, timeout=120
        )
        texto = relatorio.read_text(encoding="utf-8") if relatorio.exists() else "(sem relatório)"
    print(texto)
    if resultado.returncode != 0:
        raise SystemExit(f"Verificação do executável falhou (código {resultado.returncode})")


def sufixo_plataforma() -> str:
    sistema = {"win32": "windows", "linux": "linux"}.get(sys.platform, sys.platform)
    maquina = platform.machine().lower().replace("amd64", "x64").replace("x86_64", "x64")
    return f"{sistema}-{maquina}"


def compactar(pasta: Path) -> Path:
    base = DIST / f"{NOME}-{versao()}-{sufixo_plataforma()}"
    if sys.platform == "win32":
        destino = base.with_name(base.name + ".zip")  # with_suffix trocaria o ".0" da versão
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for arquivo in pasta.rglob("*"):
                z.write(arquivo, Path(NOME) / arquivo.relative_to(pasta))
    else:
        destino = base.with_name(base.name + ".tar.gz")
        with tarfile.open(destino, "w:gz") as t:
            t.add(pasta, arcname=NOME)
    print(f"Pacote: {destino} ({destino.stat().st_size / 2**20:.0f} MB)")
    return destino


def appimage(pasta: Path) -> Path:
    """Monta um AppDir em volta da pasta do PyInstaller e gera o AppImage."""
    appdir = DIST / "AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(pasta, appdir / "usr" / "bin")
    (appdir / "AppRun").write_text(
        '#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/usr/bin/ags-media-chrono" "$@"\n'
    )
    (appdir / "AppRun").chmod(0o755)
    shutil.copy(
        RAIZ / "src" / "ags_media_chrono" / "recursos" / "icone.png", appdir / f"{NOME}.png"
    )
    (appdir / f"{NOME}.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=AGS Media Chrono\n"
        f"Exec={NOME}\nIcon={NOME}\nCategories=Graphics;Photography;\n"
        "Comment=Datas de fotos e vídeos e renomeação em lote\n"
    )
    ferramenta = DIST / "appimagetool.AppImage"
    if not ferramenta.exists():
        urllib.request.urlretrieve(APPIMAGETOOL, ferramenta)
        ferramenta.chmod(ferramenta.stat().st_mode | stat.S_IEXEC)
    destino = DIST / f"{NOME}-{versao()}-{sufixo_plataforma()}.AppImage"
    # --appimage-extract-and-run: funciona em CI sem FUSE
    rodar(str(ferramenta), "--appimage-extract-and-run", str(appdir), str(destino),
          env={**os.environ, "ARCH": platform.machine()})  # fmt: skip
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sem-appimage", action="store_true", help="Linux: não gerar AppImage")
    parser.add_argument("--sem-verificar", action="store_true", help="não testar o executável")
    args = parser.parse_args()

    pasta = pyinstaller()
    if not args.sem_verificar:
        verificar(pasta)
    compactar(pasta)
    if sys.platform.startswith("linux") and not args.sem_appimage:
        print(f"AppImage: {appimage(pasta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
