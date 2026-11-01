"""Cria uma pasta de demonstração com fotos e vídeos sintéticos (sem fotos de pessoas).

Cada arquivo imita uma origem real — iPhone (HEIC/MOV), WhatsApp, câmera Nikon, captura de
tela, exportação do iCloud — com os metadados típicos dela, e todos ficam com a data do
arquivo "errada" (a do download), como acontece ao baixar do iCloud.

Uso:
    python tools/criar_demo.py PASTA_DESTINO
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pillow_heif
from PIL import Image, ImageDraw, ImageFilter, ImageOps

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from ags_media_chrono.core.exiftool import ExifTool  # noqa: E402
from ags_media_chrono.core.ferramentas import localizar  # noqa: E402

pillow_heif.register_heif_opener()

PAISAGEM, RETRATO = (1600, 1067), (1067, 1600)
DATA_DO_DOWNLOAD = datetime(2026, 10, 30, 9, 15).timestamp()


# --- desenhos ------------------------------------------------------------------------------


def _ceu(tamanho, topo, base) -> Image.Image:
    gradiente = Image.linear_gradient("L").resize(tamanho)
    return ImageOps.colorize(gradiente, topo, base).convert("RGB")


def _montanhas(imagem, rnd, camadas) -> None:
    largura, altura = imagem.size
    desenho = ImageDraw.Draw(imagem)
    for i, cor in enumerate(camadas):
        base = altura * (0.55 + 0.12 * i)
        pontos = [(0, altura)]
        for x in range(0, largura + 80, 80):
            pontos.append((x, base - rnd.randint(0, int(altura * 0.18))))
        pontos.append((largura, altura))
        desenho.polygon(pontos, fill=cor)


def por_do_sol(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    img = _ceu(tamanho, "#2b1d4a", "#f28c38")
    d = ImageDraw.Draw(img)
    cx, cy, r = tamanho[0] * 0.62, tamanho[1] * 0.52, tamanho[0] * 0.07
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#ffd27a")
    _montanhas(img, rnd, ["#5a2f5c", "#3b2148", "#1f1430"])
    return img.filter(ImageFilter.GaussianBlur(1))


def praia(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    largura, altura = tamanho
    img = _ceu(tamanho, "#3d7fc4", "#bfe3f5")
    d = ImageDraw.Draw(img)
    d.rectangle((0, altura * 0.55, largura, altura * 0.75), fill="#1f6f99")
    for _ in range(40):
        y = rnd.uniform(altura * 0.56, altura * 0.74)
        x = rnd.uniform(0, largura)
        d.line((x, y, x + rnd.uniform(30, 120), y), fill="#7fc3e0", width=2)
    d.rectangle((0, altura * 0.75, largura, altura), fill="#e8cf9a")
    for _ in range(6):
        x, y = rnd.uniform(0, largura), rnd.uniform(altura * 0.08, altura * 0.35)
        for dx in (0, 40, 80):
            d.ellipse((x + dx, y, x + dx + 90, y + 45), fill="#f4f8fb")
    return img.filter(ImageFilter.GaussianBlur(1.2))


def noite(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    largura, altura = tamanho
    img = _ceu(tamanho, "#050914", "#1c2b55")
    d = ImageDraw.Draw(img)
    for _ in range(500):
        x, y, r = rnd.uniform(0, largura), rnd.uniform(0, altura * 0.7), rnd.choice((1, 1, 1, 2))
        d.ellipse((x, y, x + r, y + r), fill=(255, 255, 255, rnd.randint(120, 255)))
    cx, cy, r = largura * 0.25, altura * 0.22, largura * 0.05
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill="#f1efe2")
    _montanhas(img, rnd, ["#141a2e", "#0b0f1c"])
    return img


def floresta(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    largura, altura = tamanho
    img = _ceu(tamanho, "#a9d4c2", "#e9f2d8")
    d = ImageDraw.Draw(img)
    for camada, cor in enumerate(("#6f9e7c", "#477a5a", "#2b5a3e", "#173d29")):
        base = altura * (0.45 + 0.15 * camada)
        for _ in range(28):
            x = rnd.uniform(-50, largura)
            h = rnd.uniform(altura * 0.15, altura * 0.35)
            w = h * 0.45
            d.polygon([(x, base), (x + w / 2, base - h), (x + w, base)], fill=cor)
        d.rectangle((0, base, largura, altura), fill=cor)
    return img.filter(ImageFilter.GaussianBlur(0.8))


def cidade(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    largura, altura = tamanho
    img = _ceu(tamanho, "#1b1440", "#e0637a")
    d = ImageDraw.Draw(img)
    x = 0
    while x < largura:
        w, h = rnd.randint(70, 160), rnd.uniform(altura * 0.25, altura * 0.7)
        topo = altura - h
        d.rectangle((x, topo, x + w, altura), fill="#151226")
        for jy in range(int(topo) + 15, altura - 10, 28):
            for jx in range(x + 10, x + w - 10, 22):
                if rnd.random() < 0.45:
                    d.rectangle((jx, jy, jx + 9, jy + 13), fill=rnd.choice(("#ffd98a", "#ffeab8")))
        x += w + rnd.randint(4, 14)
    return img


def aurora(tamanho, semente) -> Image.Image:
    rnd = random.Random(semente)
    largura, altura = tamanho
    img = _ceu(tamanho, "#030a12", "#0f2b33")
    faixa = Image.new("RGB", tamanho, "black")
    d = ImageDraw.Draw(faixa)
    for i in range(5):
        y = altura * (0.15 + 0.08 * i)
        pontos = [(x, y + 60 * rnd.random()) for x in range(0, largura + 100, 100)]
        d.line(pontos, fill=rnd.choice(("#39e6a0", "#2bc4d9", "#8af08a")), width=60)
    faixa = faixa.filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(img, faixa, 0.55)
    _montanhas(img, rnd, ["#06111a"])
    return img


# --- vídeos ---------------------------------------------------------------------------------


def video(destino: Path, fonte: str, tamanho: str, segundos: int = 4) -> None:
    subprocess.run(
        [str(localizar("ffmpeg")), "-v", "error", "-y", "-f", "lavfi", "-i",
         f"{fonte}=size={tamanho}:rate=25", "-t", str(segundos), "-pix_fmt", "yuv420p",
         "-q:v", "3", str(destino)],
        check=True,
    )  # fmt: skip


# --- montagem da pasta ----------------------------------------------------------------------


def criar(pasta: Path) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    criados: list[Path] = []

    def foto(nome, desenho, tamanho, semente, formato="JPEG", tags=None):
        caminho = pasta / nome
        desenho(tamanho, semente).save(caminho, format=formato, quality=88)
        criados.append(caminho)
        return caminho, tags or {}

    iphone = {"EXIF:Make": "Apple", "EXIF:Model": "iPhone 15", "EXIF:OffsetTimeOriginal": "-03:00",
              "EXIF:OffsetTime": "-03:00"}  # fmt: skip
    nikon = {"EXIF:Make": "NIKON CORPORATION", "EXIF:Model": "NIKON D3400"}

    def captura(data):
        return {"EXIF:DateTimeOriginal": data, "EXIF:CreateDate": data, "EXIF:ModifyDate": data}

    itens = [
        foto("IMG_4821.HEIC", por_do_sol, PAISAGEM, 1, "HEIF",
             {**iphone, **captura("2024:07:14 18:42:10")}),
        foto("IMG_4822.HEIC", praia, PAISAGEM, 2, "HEIF",
             {**iphone, **captura("2024:07:15 10:05:31")}),
        foto("IMG_5102.JPG", floresta, RETRATO, 3,
             tags={**iphone, **captura("2024:08:03 07:58:44")}),
        foto("DSC_0231.JPG", noite, PAISAGEM, 4, tags={**nikon, **captura("2023:12:24 21:10:05")}),
        foto("DSC_0232.JPG", aurora, PAISAGEM, 5, tags={**nikon, **captura("2023:12:24 21:16:40")}),
        foto("IMG-20240315-WA0012.jpg", cidade, RETRATO, 6),  # WhatsApp: sem metadados
        foto("IMG-20240318-WA0004.jpg", praia, RETRATO, 7),
        foto("Screenshot_20240402-101530.png", aurora, RETRATO, 8, "PNG"),
    ]  # fmt: skip

    videos = [
        # iPhone: QuickTime em UTC + Keys:CreationDate local
        ("IMG_4830.MOV", "mandelbrot", "360x640",
         {"QuickTime:CreateDate": "2024:07:14 22:01:12", "QuickTime:TrackCreateDate":
          "2024:07:14 22:01:12", "QuickTime:MediaCreateDate": "2024:07:14 22:01:12",
          "Keys:CreationDate": "2024:07:14 19:01:12-03:00", "Keys:Make": "Apple",
          "Keys:Model": "iPhone 15"}),
        # WhatsApp: datas internas zeradas
        ("VID-20240316-WA0003.mp4", "cellauto", "640x360", {}),
        # Exportação do iCloud com nome aleatório (só QuickTime em UTC)
        ("7F3A9C21-4B1E-4D2A-9E55-0C8D2B6A1F40.mov", "gradients", "640x360",
         {"QuickTime:CreateDate": "2024:08:03 11:20:05", "QuickTime:TrackCreateDate":
          "2024:08:03 11:20:05", "QuickTime:MediaCreateDate": "2024:08:03 11:20:05"}),
    ]  # fmt: skip
    for nome, fonte, tamanho, tags in videos:
        caminho = pasta / nome
        video(caminho, fonte, tamanho)
        criados.append(caminho)
        itens.append((caminho, tags))

    with ExifTool() as et:
        for caminho, tags in itens:
            if tags:
                resultado = et.gravar(caminho, tags)
                if not resultado.ok:
                    raise RuntimeError(f"{caminho.name}: {resultado.erros}")
    for caminho in criados:  # o "problema": data do arquivo = dia do download
        os.utime(caminho, (DATA_DO_DOWNLOAD, DATA_DO_DOWNLOAD))
    return criados


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    criados = criar(Path(argv[0]))
    print(f"{len(criados)} arquivos criados em {Path(argv[0]).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
