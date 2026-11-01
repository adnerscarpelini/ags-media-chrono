"""Datas embutidas no nome do arquivo.

Padrões cobertos (exemplos):
- WhatsApp celular:   IMG-20230512-WA0001.jpg, VID-20230512-WA0003.mp4 (só a data)
- WhatsApp desktop:   WhatsApp Image 2023-05-12 at 14.30.00.jpeg (também com AM/PM)
                      Imagem do WhatsApp de 2023-05-12 à(s) 14.30.00_8f3a2b1c.jpg
- Android / Samsung:  IMG_20230512_143000.jpg, VID_20230512_143000.mp4, 20230512_143000.jpg,
                      IMG20230512143000.jpg (OPPO/realme)
- Google Pixel:       PXL_20230512_173000123.jpg (horário em UTC)
- Capturas de tela:   Screenshot_20230512-143000.png, Screenshot 2023-05-12 at 14.30.00.png,
                      Captura de tela 2023-05-12 143000.png
- Signal / Telegram:  signal-2023-05-12-143000.jpg, photo_2023-05-12_14-30-00.jpg
- Genéricos:          2023-05-12 14.30.00.jpg, 2026_festa_20261101_0001.jpg (só a data)

Nomes sem data (IMG_1234.JPG, DSC_0105.JPG, UUIDs do iCloud) não geram candidata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

_PIXEL = re.compile(
    r"^PXL_(?P<ano>\d{4})(?P<mes>\d{2})(?P<dia>\d{2})_(?P<h>\d{2})(?P<min>\d{2})(?P<s>\d{2})"
)
_WHATSAPP_CELULAR = re.compile(
    r"^(?:IMG|VID|AUD|PTT|STK|DOC)-(?P<ano>\d{4})(?P<mes>\d{2})(?P<dia>\d{2})-WA\d+",
    re.IGNORECASE,
)
_SEPARADOR_HORA = r"(?:[ _T.-]|\s+at\s+|\s+à\(s\)\s+|\s+às\s+)"
_GENERICO = re.compile(
    r"(?<!\d)(?P<ano>(?:19|20)\d{2})[-_.]?(?P<mes>\d{2})[-_.]?(?P<dia>\d{2})"
    rf"(?:{_SEPARADOR_HORA}?(?P<h>\d{{1,2}})[-_.:h]?(?P<min>\d{{2}})[-_.:m]?(?P<s>\d{{2}})"
    r"(?:\s?(?P<ampm>[AaPp][Mm]))?)?"
    r"(?!\d)",
    re.IGNORECASE,
)
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

ANO_MINIMO = 1990

# (prefixo do nome em minúsculas, rótulo)
_ROTULOS = (
    (("whatsapp", "imagem do whatsapp", "vídeo do whatsapp", "video do whatsapp"), "WhatsApp"),
    (("screenshot", "screen shot", "captura de tela", "screen_recording", "screenrecord"),
     "captura de tela"),
    (("img_", "vid_", "img2", "vid2"), "Android"),
    (("signal",), "Signal"),
    (("photo_", "video_"), "Telegram"),
)  # fmt: skip


def _rotulo(nome: str) -> str:
    minusculo = nome.casefold()
    for prefixos, rotulo in _ROTULOS:
        if minusculo.startswith(prefixos):
            return f"Data no nome do arquivo ({rotulo})"
    return "Data no nome do arquivo"


def _montar(m: re.Match, *, utc: bool = False) -> tuple[datetime, bool] | None:
    """Monta a data validando limites; se a hora for inválida, fica só a data."""
    try:
        dia = date(int(m["ano"]), int(m["mes"]), int(m["dia"]))
    except ValueError:
        return None
    if not ANO_MINIMO <= dia.year <= date.today().year + 1:
        return None

    grupos = m.groupdict()
    if grupos.get("h") is None:
        return datetime(dia.year, dia.month, dia.day), True
    h, minuto, s = int(m["h"]), int(m["min"]), int(m["s"])
    ampm = (grupos.get("ampm") or "").lower()
    if ampm:
        if not 1 <= h <= 12:
            return datetime(dia.year, dia.month, dia.day), True
        h = h % 12 + (12 if ampm == "pm" else 0)
    if h > 23 or minuto > 59 or s > 59:
        return datetime(dia.year, dia.month, dia.day), True
    valor = datetime(dia.year, dia.month, dia.day, h, minuto, s)
    return (valor.replace(tzinfo=UTC) if utc else valor), False


@dataclass(frozen=True)
class DataNoNome:
    valor: datetime  # com tzinfo UTC no caso do Pixel; senão horário local sem fuso
    somente_data: bool
    rotulo: str


def data_do_nome(nome: str) -> DataNoNome | None:
    """Data encontrada no nome do arquivo (a do padrão mais específico) ou None."""
    base = nome.rsplit(".", 1)[0] if "." in nome else nome

    if m := _PIXEL.match(base):
        resultado, rotulo = _montar(m, utc=True), "Data no nome do arquivo (Pixel, UTC)"
    elif m := _WHATSAPP_CELULAR.match(base):
        resultado, rotulo = _montar(m), "Data no nome do arquivo (WhatsApp)"
    elif _UUID.search(base):
        return None  # nomes de exportação do iCloud: os dígitos são aleatórios
    else:
        # Prefere um trecho com data e hora; senão fica com a primeira data válida.
        resultado = None
        for m in _GENERICO.finditer(base):
            tentativa = _montar(m)
            if tentativa is None:
                continue
            if resultado is None or not tentativa[1]:
                resultado = tentativa
            if not tentativa[1]:
                break
        rotulo = _rotulo(base)

    if resultado is None:
        return None
    valor, somente_data = resultado
    return DataNoNome(valor, somente_data, rotulo)
