"""Leitura de todas as datas encontradas em um arquivo de mídia.

Cada data vira uma `DataCandidata`, com a origem (EXIF, XMP, QuickTime...), o campo exato e o
valor. O usuário escolhe qual é a correta (issue #14). Este módulo só lê e interpreta; a
normalização de fusos para exibição fica na issue #13 e as datas do nome do arquivo na #12.

Uso pela linha de comando (diagnóstico):
    python -m ags_media_chrono.core.datas arquivo1.jpg arquivo2.mov ...
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path

from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.nome_arquivo import data_do_nome


class Origem(StrEnum):
    EXIF = "EXIF"
    XMP = "XMP"
    QUICKTIME = "QuickTime"
    IPTC = "IPTC"
    FABRICANTE = "Fabricante"
    GPS = "GPS"
    ARQUIVO = "Sistema de arquivos"
    NOME = "Nome do arquivo"
    OUTRO = "Outro"


@dataclass(frozen=True)
class DataCandidata:
    origem: Origem
    campo: str  # nome ExifTool com grupo, ex.: "ExifIFD:DateTimeOriginal"
    rotulo: str  # descrição para o usuário
    valor: datetime  # com tzinfo quando o fuso é conhecido
    texto: str  # valor original, como o ExifTool retornou
    captura: bool = False  # representa o momento da captura?
    prioridade: int = 100  # entre as datas de captura, menor = mais confiável
    utc_presumido: bool = False  # campos QuickTime: a especificação manda gravar em UTC
    somente_data: bool = False  # sem hora (ex.: alguns XMP/IPTC)

    @property
    def fuso(self) -> timedelta | None:
        return self.valor.utcoffset()


@dataclass
class DatasArquivo:
    arquivo: Path
    candidatas: list[DataCandidata] = field(default_factory=list)
    erro: str | None = None
    # Fuso configurado na câmera (EXIF OffsetTime* ou TimeZone + horário de verão da Nikon).
    fuso_camera: timedelta | None = None

    def captura_sugerida(self) -> DataCandidata | None:
        """Data de captura mais confiável, base da pré-seleção (issue #14)."""
        capturas = [c for c in self.candidatas if c.captura]
        return min(capturas, key=lambda c: c.prioridade) if capturas else None

    # --- fusos (issue #13) ---------------------------------------------------------------

    def fuso_referencia(self) -> timedelta | None:
        """Fuso em que as datas deste arquivo são exibidas (o "relógio" de onde foi capturado).

        Ordem: fuso da câmera; fuso de uma data de captura que traga fuso (ex.: Keys:CreationDate
        do iPhone), exceto UTC puro. None = usar o fuso do sistema.
        """
        if self.fuso_camera is not None:
            return self.fuso_camera
        capturas = sorted((c for c in self.candidatas if c.captura), key=lambda c: c.prioridade)
        for c in capturas:
            if c.fuso is not None and c.fuso != timedelta(0):
                return c.fuso
        return None

    def instante(self, c: DataCandidata, opcoes: OpcoesFuso | None = None) -> datetime:
        """Momento absoluto (datetime com fuso) que a candidata representa."""
        opcoes = opcoes or OpcoesFuso()
        if c.valor.tzinfo is not None:
            return c.valor
        if c.utc_presumido and opcoes.quicktime_utc:
            return c.valor.replace(tzinfo=UTC)
        fuso = self.fuso_referencia()
        if fuso is None:
            fuso = opcoes.fuso_padrao
        if fuso is not None:
            return c.valor.replace(tzinfo=timezone(fuso))
        return c.valor.astimezone()  # sem fuso conhecido: horário local do sistema

    def hora_local(self, c: DataCandidata, opcoes: OpcoesFuso | None = None) -> datetime:
        """A candidata convertida para o fuso de referência do arquivo, para exibição/comparação."""
        opcoes = opcoes or OpcoesFuso()
        momento = self.instante(c, opcoes)
        fuso = self.fuso_referencia()
        if fuso is None:
            fuso = opcoes.fuso_padrao
        return momento.astimezone(timezone(fuso)) if fuso is not None else momento.astimezone()


@dataclass(frozen=True)
class OpcoesFuso:
    # A especificação QuickTime manda gravar CreateDate em UTC (iPhone, a maioria das câmeras).
    # Alguns aparelhos gravam o horário local; para esses, desligue esta opção.
    quicktime_utc: bool = True
    # Fuso usado quando o arquivo não indica nenhum. None = fuso do sistema na data.
    fuso_padrao: timedelta | None = None


def formatar_data(valor: datetime, somente_data: bool = False) -> str:
    """28/10/2026 10:00:08 (ou só 28/10/2026)."""
    return valor.strftime("%d/%m/%Y" if somente_data else "%d/%m/%Y %H:%M:%S")


# --- regras ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Regra:
    rotulo: str
    captura: bool = False
    prioridade: int = 100
    offset: str | None = None  # campo com o fuso correspondente (EXIF 2.31+)


# Campos conhecidos (grupo:tag). Campos de data fora desta tabela também entram, como
# "não captura", para que o usuário veja todas as datas existentes.
_REGRAS: dict[str, _Regra] = {
    # EXIF
    "ExifIFD:DateTimeOriginal": _Regra("Data de captura", True, 10, "ExifIFD:OffsetTimeOriginal"),
    "IFD0:DateTimeOriginal": _Regra("Data de captura (IFD0)", True, 15),
    "ExifIFD:CreateDate": _Regra("Data de digitalização", True, 30, "ExifIFD:OffsetTimeDigitized"),
    "IFD0:ModifyDate": _Regra("Data de modificação", offset="ExifIFD:OffsetTime"),
    # QuickTime / vídeos
    "Keys:CreationDate": _Regra("Data de criação (Apple)", True, 10),
    "UserData:DateTimeOriginal": _Regra("Data de captura (UserData)", True, 20),
    "QuickTime:CreationDate": _Regra("Data de criação", True, 20),
    "ItemList:ContentCreateDate": _Regra("Data de criação do conteúdo", True, 35),
    "QuickTime:CreateDate": _Regra("Data de criação", True, 40),
    "QuickTime:ModifyDate": _Regra("Data de modificação"),
    "Track:TrackCreateDate": _Regra("Criação da faixa", True, 45),
    "Track:MediaCreateDate": _Regra("Criação da mídia", True, 45),
    "Track:TrackModifyDate": _Regra("Modificação da faixa"),
    "Track:MediaModifyDate": _Regra("Modificação da mídia"),
    # XMP
    "XMP-exif:DateTimeOriginal": _Regra("Data de captura", True, 20),
    "XMP-photoshop:DateCreated": _Regra("Data de criação (Photoshop)", True, 25),
    "XMP-xmp:CreateDate": _Regra("Data de criação", True, 30),
    "XMP-xmp:ModifyDate": _Regra("Data de modificação"),
    "XMP-xmp:MetadataDate": _Regra("Data de edição dos metadados"),
    # IPTC (DateCreated + TimeCreated combinados pelo ExifTool)
    "Composite:DateTimeCreated": _Regra("Data de criação", True, 25),
    # GPS (sempre UTC)
    "Composite:GPSDateTime": _Regra("Data/hora do GPS (UTC)", True, 50),
    # Sistema de arquivos
    "System:FileCreateDate": _Regra("Data de criação do arquivo"),
    "System:FileModifyDate": _Regra("Data de modificação do arquivo"),
}

# Campos que são datas mas não ajudam (ou são duplicatas de outros campos).
_IGNORAR = re.compile(
    r"^(System:FileAccessDate|System:FileInodeChangeDate|ICC[-\w]*:ProfileDateTime"
    r"|Composite:SubSec\w+|Composite:(?!GPSDateTime$|DateTimeCreated$)\w+"
    r"|IPTC:(DateCreated|TimeCreated|DigitalCreationDate|DigitalCreationTime)"
    r"|GPS:\w+|Nikon:PowerUpTime|XMP-xmpMM:.*|ExifTool:.*)$"
)

_GRUPOS_FABRICANTE = re.compile(
    r"^(Nikon\w*|Canon\w*|Sony\w*|Apple|Samsung\w*|FujiFilm|Olympus\w*|Panasonic\w*"
    r"|Pentax\w*|Ricoh\w*|Sigma\w*|Leica\w*|DJI\w*|GoPro\w*|MakerNotes)$"
)


def _origem_do_grupo(grupo: str) -> Origem:
    if grupo in ("ExifIFD", "IFD0", "IFD1", "SubIFD", "InteropIFD"):
        return Origem.EXIF
    if grupo.startswith("XMP"):
        return Origem.XMP
    if grupo in ("QuickTime", "Keys", "UserData", "ItemList", "Track") or grupo.startswith("Track"):
        return Origem.QUICKTIME
    if grupo in ("IPTC", "Composite"):
        return Origem.IPTC
    if grupo == "System":
        return Origem.ARQUIVO
    if _GRUPOS_FABRICANTE.match(grupo):
        return Origem.FABRICANTE
    return Origem.OUTRO


# --- interpretação dos valores ------------------------------------------------------------------

_DATA = re.compile(
    r"^(?P<ano>\d{4}):(?P<mes>\d{2}):(?P<dia>\d{2})"
    r"(?:[ T](?P<h>\d{2}):(?P<m>\d{2})(?::(?P<s>\d{2})(?:\.\d+)?)?)?"
    r"\s*(?P<fuso>Z|[+-]\d{2}:?\d{2})?(?:\s*DST)?$"
)
_FUSO = re.compile(r"^(?P<sinal>[+-])(?P<h>\d{2}):?(?P<m>\d{2})$")

# Datas "zero" de alguns formatos (QuickTime usa 1904, Unix 1970) indicam campo vazio.
_DATAS_VAZIAS = {datetime(1904, 1, 1), datetime(1970, 1, 1)}
ANO_MINIMO = 1900


def interpretar_fuso(texto: str) -> timedelta | None:
    texto = texto.strip()
    if texto == "Z":
        return timedelta(0)
    m = _FUSO.match(texto)
    if not m:
        return None
    delta = timedelta(hours=int(m["h"]), minutes=int(m["m"]))
    return -delta if m["sinal"] == "-" else delta


def formatar_fuso(fuso: timedelta) -> str:
    """timedelta(hours=-3) -> "-03:00"."""
    minutos = int(fuso.total_seconds()) // 60
    sinal = "-" if minutos < 0 else "+"
    h, m = divmod(abs(minutos), 60)
    return f"{sinal}{h:02d}:{m:02d}"


def interpretar_data(texto: str) -> tuple[datetime, bool] | None:
    """Converte o formato do ExifTool ("2023:05:12 14:30:00-03:00") em datetime.

    Retorna (data, somente_data) ou None para valores vazios/zerados/inválidos.
    """
    m = _DATA.match(str(texto).strip())
    if not m:
        return None
    try:
        valor = datetime(
            int(m["ano"]), int(m["mes"]), int(m["dia"]),
            int(m["h"] or 0), int(m["m"] or 0), int(m["s"] or 0),
        )  # fmt: skip
    except ValueError:  # 0000:00:00, mês 13 etc.
        return None
    if valor.year < ANO_MINIMO or valor in _DATAS_VAZIAS:
        return None
    if m["fuso"]:
        fuso = interpretar_fuso(m["fuso"])
        if fuso is not None:
            valor = valor.replace(tzinfo=timezone(fuso))
    return valor, m["h"] is None


def _fuso_camera(tags: Mapping[str, object]) -> timedelta | None:
    for campo in ("ExifIFD:OffsetTimeOriginal", "ExifIFD:OffsetTime"):
        if campo in tags and (fuso := interpretar_fuso(str(tags[campo]))) is not None:
            return fuso
    # Nikon: TimeZone não inclui o horário de verão, que vem em DaylightSavings.
    fuso = interpretar_fuso(str(tags.get("Nikon:TimeZone", "")))
    if fuso is None:
        return None
    if str(tags.get("Nikon:DaylightSavings", "")).lower() in ("yes", "on", "1"):
        fuso += timedelta(hours=1)
    return fuso


def candidatas_de_tags(tags: Mapping[str, object]) -> list[DataCandidata]:
    """Extrai as datas de um dicionário de tags no formato `-json -G1` do ExifTool."""
    candidatas: list[DataCandidata] = []
    vistos: set[tuple[str, str]] = set()

    for campo, bruto in tags.items():
        if ":" not in campo or _IGNORAR.match(campo):
            continue
        texto = str(bruto)
        interpretado = interpretar_data(texto)
        if interpretado is None:
            continue
        valor, somente_data = interpretado

        grupo, tag = campo.split(":", 1)
        # Vídeos repetem as mesmas datas em cada faixa (Track1, Track2...): agrupa.
        chave_regra = f"Track:{tag}" if re.fullmatch(r"Track\d+", grupo) else campo
        if (chave_regra, texto) in vistos:
            continue
        vistos.add((chave_regra, texto))

        regra = _REGRAS.get(chave_regra) or _Regra(tag)
        if regra.offset and valor.tzinfo is None and regra.offset in tags:
            fuso = interpretar_fuso(str(tags[regra.offset]))
            if fuso is not None:
                valor = valor.replace(tzinfo=timezone(fuso))

        origem = _origem_do_grupo(grupo)
        if campo == "Composite:GPSDateTime":
            origem = Origem.GPS
        candidatas.append(
            DataCandidata(
                origem=origem,
                campo=campo if chave_regra == campo else chave_regra,
                rotulo=regra.rotulo,
                valor=valor,
                texto=texto,
                captura=regra.captura,
                prioridade=regra.prioridade,
                utc_presumido=origem == Origem.QUICKTIME
                and grupo != "Keys"
                and valor.tzinfo is None,
                somente_data=somente_data,
            )
        )
    return candidatas


# --- leitura --------------------------------------------------------------------------------

# ExifTool:Error precisa ser pedido explicitamente: com uma lista de tags, o ExifTool só
# devolve as tags pedidas e o erro de arquivo vazio/corrompido sumiria da resposta.
TAGS_LEITURA = ("time:all", "Nikon:TimeZone", "Nikon:DaylightSavings", "ExifTool:Error")


def ler_datas(
    arquivos: Iterable[str | Path],
    exiftool: ExifTool,
    *,
    progresso: Callable[[int, int], None] | None = None,
) -> list[DatasArquivo]:
    resultados = []
    for leitura in exiftool.ler(arquivos, TAGS_LEITURA, progresso=progresso):
        if not leitura.ok:
            resultados.append(DatasArquivo(leitura.arquivo, erro=leitura.erro))
            continue
        candidatas = candidatas_de_tags(leitura.tags)
        if (do_nome := candidata_do_nome(leitura.arquivo.name)) is not None:
            candidatas.append(do_nome)
        resultados.append(
            DatasArquivo(
                leitura.arquivo,
                candidatas=candidatas,
                fuso_camera=_fuso_camera(leitura.tags),
            )
        )
    return resultados


def candidata_do_nome(nome: str) -> DataCandidata | None:
    encontrada = data_do_nome(nome)
    if encontrada is None:
        return None
    return DataCandidata(
        origem=Origem.NOME,
        campo="Nome:Arquivo",
        rotulo=encontrada.rotulo,
        valor=encontrada.valor,
        texto=nome,
        captura=False,  # não é metadado de captura: fica fora da pré-seleção (#14)
        somente_data=encontrada.somente_data,
    )


def _main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with ExifTool() as et:
        for r in ler_datas(argv, et):
            print(f"\n== {r.arquivo}")
            if r.erro:
                print(f"   ERRO: {r.erro}")
                continue
            referencia = r.fuso_referencia()
            if referencia is not None:
                print(f"   fuso de referência: {formatar_fuso(referencia)}")
            sugerida = r.captura_sugerida()
            for c in sorted(r.candidatas, key=lambda c: r.instante(c)):
                marca = "*" if c is sugerida else " "
                local = formatar_data(r.hora_local(c), c.somente_data)
                extras = " ".join(
                    x
                    for x, ativo in (("(era UTC)", c.utc_presumido), ("captura", c.captura))
                    if ativo
                )
                print(f" {marca} {local:<20} {c.origem.value:<20} {c.campo:<30} {extras}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
