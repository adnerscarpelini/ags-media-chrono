"""Baixa ExifTool e FFmpeg para tools/bin/ (Windows e Linux).

Uso:
    python tools/baixar_ferramentas.py              # baixa o que estiver faltando
    python tools/baixar_ferramentas.py --forcar     # baixa tudo de novo
    python tools/baixar_ferramentas.py --somente exiftool

Usa apenas a biblioteca padrão do Python. Todo download é conferido por SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PASTA_BIN = Path(__file__).resolve().parent / "bin"
ARQUIVO_VERSOES = PASTA_BIN / "versoes.json"

EXIFTOOL_URL = "https://exiftool.org"
# Os pacotes são hospedados no SourceForge; ver.txt e checksums.txt ficam em exiftool.org.
EXIFTOOL_DOWNLOAD = "https://sourceforge.net/projects/exiftool/files/{nome}/download"
FFMPEG_SERIE = "8.1"
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"

WINDOWS = sys.platform == "win32"
EXE = ".exe" if WINDOWS else ""


class ErroDownload(Exception):
    pass


def baixar_texto(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8")


def baixar_arquivo(url: str, destino: Path) -> None:
    print(f"  baixando {url}")
    with urllib.request.urlopen(url, timeout=60) as resp, open(destino, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        lido = 0
        ultimo = -1
        while bloco := resp.read(1024 * 256):
            f.write(bloco)
            lido += len(bloco)
            pct = lido * 100 // total if total else 0
            if total and pct // 10 != ultimo:
                ultimo = pct // 10
                print(f"  {pct:3d}% de {total // (1024 * 1024)} MB")


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while bloco := f.read(1024 * 1024):
            h.update(bloco)
    return h.hexdigest()


def conferir_sha256(caminho: Path, esperado: str) -> None:
    obtido = sha256(caminho)
    if obtido.lower() != esperado.lower():
        raise ErroDownload(
            f"Checksum inválido para {caminho.name}: esperado {esperado}, obtido {obtido}"
        )
    print("  checksum OK")


def parse_checksums_exiftool(texto: str) -> dict[str, str]:
    """Lê linhas no formato 'SHA2-256(arquivo)= hash'."""
    return dict(re.findall(r"^SHA2-256\((.+?)\)=\s*([0-9a-fA-F]{64})\s*$", texto, re.MULTILINE))


def parse_checksums_sha256sum(texto: str) -> dict[str, str]:
    """Lê linhas no formato do sha256sum: 'hash  arquivo'."""
    return {nome: h for h, nome in re.findall(r"^([0-9a-fA-F]{64})\s+\*?(\S+)\s*$", texto, re.M)}


def extrair(arquivo: Path, destino: Path) -> None:
    if arquivo.suffix == ".zip":
        with zipfile.ZipFile(arquivo) as z:
            z.extractall(destino)
    else:
        with tarfile.open(arquivo) as t:
            if hasattr(tarfile, "data_filter"):
                t.extractall(destino, filter="data")
            else:
                t.extractall(destino)


def unica_subpasta(pasta: Path) -> Path:
    itens = [p for p in pasta.iterdir() if p.is_dir()]
    if len(itens) != 1:
        raise ErroDownload(f"Estrutura inesperada no pacote: {[p.name for p in pasta.iterdir()]}")
    return itens[0]


def tornar_executavel(caminho: Path) -> None:
    if not WINDOWS:
        caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def instalar_exiftool(tmp: Path) -> str:
    versao = baixar_texto(f"{EXIFTOOL_URL}/ver.txt").strip()
    nome = f"exiftool-{versao}_64.zip" if WINDOWS else f"Image-ExifTool-{versao}.tar.gz"
    checksums = parse_checksums_exiftool(baixar_texto(f"{EXIFTOOL_URL}/checksums.txt"))
    if nome not in checksums:
        raise ErroDownload(f"Checksum de {nome} não encontrado em checksums.txt")

    pacote = tmp / nome
    baixar_arquivo(EXIFTOOL_DOWNLOAD.format(nome=nome), pacote)
    conferir_sha256(pacote, checksums[nome])
    extrair(pacote, tmp / "exiftool")
    origem = unica_subpasta(tmp / "exiftool")

    destino = PASTA_BIN / "exiftool"
    shutil.rmtree(destino, ignore_errors=True)
    if WINDOWS:
        # O zip traz "exiftool(-k).exe" + pasta exiftool_files; renomear evita a pausa "-k".
        destino.mkdir(parents=True)
        shutil.move(str(origem / "exiftool(-k).exe"), destino / "exiftool.exe")
        shutil.move(str(origem / "exiftool_files"), destino / "exiftool_files")
    else:
        # Script Perl: precisa da pasta lib/ ao lado.
        destino.mkdir(parents=True)
        shutil.move(str(origem / "exiftool"), destino / "exiftool")
        shutil.move(str(origem / "lib"), destino / "lib")
        tornar_executavel(destino / "exiftool")
        if not shutil.which("perl"):
            print("  AVISO: 'perl' não encontrado. Instale-o (ex.: sudo apt install perl).")
    return versao


def nome_pacote_ffmpeg() -> str:
    maquina = platform.machine().lower()
    arm = maquina in ("arm64", "aarch64")
    if WINDOWS:
        return f"ffmpeg-n{FFMPEG_SERIE}-latest-win{'arm' if arm else ''}64-lgpl-{FFMPEG_SERIE}.zip"
    if sys.platform.startswith("linux"):
        alvo = "linuxarm64" if arm else "linux64"
        return f"ffmpeg-n{FFMPEG_SERIE}-latest-{alvo}-lgpl-{FFMPEG_SERIE}.tar.xz"
    raise ErroDownload(f"Sistema não suportado para FFmpeg: {sys.platform}")


def instalar_ffmpeg(tmp: Path) -> str:
    nome = nome_pacote_ffmpeg()
    checksums = parse_checksums_sha256sum(baixar_texto(f"{FFMPEG_URL}/checksums.sha256"))
    if nome not in checksums:
        raise ErroDownload(f"Checksum de {nome} não encontrado em checksums.sha256")

    pacote = tmp / nome
    baixar_arquivo(f"{FFMPEG_URL}/{nome}", pacote)
    conferir_sha256(pacote, checksums[nome])
    extrair(pacote, tmp / "ffmpeg")
    origem = unica_subpasta(tmp / "ffmpeg") / "bin"

    destino = PASTA_BIN / "ffmpeg"
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    for programa in ("ffmpeg", "ffprobe"):
        shutil.move(str(origem / f"{programa}{EXE}"), destino / f"{programa}{EXE}")
        tornar_executavel(destino / f"{programa}{EXE}")
    shutil.move(str(origem.parent / "LICENSE.txt"), destino / "LICENSE.txt")
    return FFMPEG_SERIE


INSTALADORES = {
    "exiftool": (instalar_exiftool, Path("exiftool") / f"exiftool{EXE}"),
    "ffmpeg": (instalar_ffmpeg, Path("ffmpeg") / f"ffmpeg{EXE}"),
}


def ler_versoes() -> dict[str, str]:
    try:
        return json.loads(ARQUIVO_VERSOES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forcar", action="store_true", help="baixa mesmo se já existir")
    parser.add_argument("--somente", choices=sorted(INSTALADORES), help="baixa só uma ferramenta")
    args = parser.parse_args(argv)

    # Evita acentos quebrados em consoles Windows que não usam UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    PASTA_BIN.mkdir(parents=True, exist_ok=True)
    versoes = ler_versoes()
    nomes = [args.somente] if args.somente else list(INSTALADORES)
    falhas = 0

    for nome in nomes:
        instalar, executavel = INSTALADORES[nome]
        if not args.forcar and (PASTA_BIN / executavel).exists():
            versao = versoes.get(nome, "?")
            print(f"[{nome}] já instalado ({versao}) — use --forcar para baixar de novo")
            continue
        print(f"[{nome}]")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                versoes[nome] = instalar(Path(tmp))
            print(f"  instalado em {PASTA_BIN / executavel.parent} (versão {versoes[nome]})")
        except Exception as e:  # noqa: BLE001 — mostrar qualquer falha e seguir para a próxima
            falhas += 1
            print(f"  ERRO: {e}")

    ARQUIVO_VERSOES.write_text(json.dumps(versoes, indent=2), encoding="utf-8")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
