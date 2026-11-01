"""Gravação da data escolhida nos metadados e no sistema de arquivos (issues #18–#21).

Para cada arquivo:
1. calcula os campos a gravar conforme o tipo (foto/vídeo) e os grupos escolhidos;
2. lê os valores atuais desses campos (para poder desfazer);
3. opcionalmente copia o original para uma pasta de backup;
4. grava tudo em um único comando do ExifTool. Se o formato não aceita metadados (BMP, AVI...),
   grava só as datas do sistema de arquivos e avisa.

Desfazer = apagar os campos gravados e restaurar os valores antigos, no mesmo comando
(no ExifTool vale a última atribuição de cada tag).
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from ags_media_chrono.core.datas import formatar_fuso
from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.historico import Operacao, TipoOperacao
from ags_media_chrono.core.midias import Midia, TipoMidia

# A data de criação do arquivo só pode ser alterada no Windows (no Linux a maioria dos
# sistemas de arquivos não permite mudar o "birth time").
SUPORTA_DATA_CRIACAO = sys.platform == "win32"

# Vídeos em contêiner QuickTime/MP4 (os únicos vídeos em que o ExifTool grava datas).
EXTENSOES_QUICKTIME = frozenset({".mov", ".mp4", ".m4v", ".3gp", ".3g2"})

TAGS_SISTEMA = ("System:FileModifyDate", "System:FileCreateDate")
_SEM_SUPORTE = ("not yet supported", "Can't currently write", "Writing of")
AVISO_SO_ARQUIVO = (
    "Este formato não permite gravar metadados; só as datas do arquivo foram alteradas."
)


class GrupoCampos(StrEnum):
    EXIF = "exif"
    XMP = "xmp"
    QUICKTIME = "quicktime"
    ARQUIVO_MODIFICACAO = "arquivo_modificacao"
    ARQUIVO_CRIACAO = "arquivo_criacao"

    @property
    def rotulo(self) -> str:
        return {
            GrupoCampos.EXIF: "EXIF das fotos (DateTimeOriginal, CreateDate, ModifyDate e fuso)",
            GrupoCampos.XMP: "XMP das fotos (CreateDate, ModifyDate, DateCreated)",
            GrupoCampos.QUICKTIME: "Datas dos vídeos (QuickTime, faixas e Keys:CreationDate)",
            GrupoCampos.ARQUIVO_MODIFICACAO: "Data de modificação do arquivo",
            GrupoCampos.ARQUIVO_CRIACAO: "Data de criação do arquivo (somente Windows)",
        }[self]


def grupos_padrao() -> frozenset[GrupoCampos]:
    grupos = set(GrupoCampos)
    if not SUPORTA_DATA_CRIACAO:
        grupos.discard(GrupoCampos.ARQUIVO_CRIACAO)
    return frozenset(grupos)


@dataclass(frozen=True)
class OpcoesGravacao:
    grupos: frozenset[GrupoCampos] = field(default_factory=grupos_padrao)
    backup: bool = False  # copiar o original antes de gravar
    quicktime_utc: bool = True  # gravar QuickTime:CreateDate em UTC (padrão da especificação)


def _data(valor: datetime) -> str:
    return valor.strftime("%Y:%m:%d %H:%M:%S")


def _data_fuso(valor: datetime) -> str:
    return _data(valor) + formatar_fuso(valor.utcoffset())


def valores_para_gravar(
    midia: Midia, final: datetime, opcoes: OpcoesGravacao | None = None
) -> dict[str, str]:
    """{tag ExifTool: valor} a gravar. `final` deve ter fuso (horário local de onde foi tirada)."""
    if final.tzinfo is None:
        raise ValueError("A data a gravar precisa ter fuso horário")
    opcoes = opcoes or OpcoesGravacao()
    grupos = opcoes.grupos
    valores: dict[str, str] = {}
    local, com_fuso, fuso = _data(final), _data_fuso(final), formatar_fuso(final.utcoffset())

    if midia.tipo == TipoMidia.FOTO:
        if GrupoCampos.EXIF in grupos:
            for tag in ("DateTimeOriginal", "CreateDate", "ModifyDate"):
                valores[f"EXIF:{tag}"] = local
            for tag in ("OffsetTimeOriginal", "OffsetTimeDigitized", "OffsetTime"):
                valores[f"EXIF:{tag}"] = fuso
        if GrupoCampos.XMP in grupos:
            for tag in ("XMP-xmp:CreateDate", "XMP-xmp:ModifyDate", "XMP-exif:DateTimeOriginal",
                        "XMP-photoshop:DateCreated"):  # fmt: skip
                valores[tag] = com_fuso
    elif midia.caminho.suffix.lower() in EXTENSOES_QUICKTIME and GrupoCampos.QUICKTIME in grupos:
        quicktime = _data(final.astimezone(UTC)) if opcoes.quicktime_utc else local
        for tag in ("CreateDate", "ModifyDate", "TrackCreateDate", "TrackModifyDate",
                    "MediaCreateDate", "MediaModifyDate"):  # fmt: skip
            valores[f"QuickTime:{tag}"] = quicktime
        valores["Keys:CreationDate"] = com_fuso

    if GrupoCampos.ARQUIVO_MODIFICACAO in grupos:
        valores["System:FileModifyDate"] = com_fuso
    if GrupoCampos.ARQUIVO_CRIACAO in grupos and SUPORTA_DATA_CRIACAO:
        valores["System:FileCreateDate"] = com_fuso
    return valores


@dataclass
class ResultadoAplicacao:
    arquivo: Path
    ok: bool
    novo: str = ""  # data gravada (com fuso)
    antes: dict[str, str] = field(default_factory=dict)  # valores anteriores (tags G1)
    escritos: list[str] = field(default_factory=list)  # tags efetivamente gravadas
    mensagem: str = ""  # erro ou aviso

    def para_entrada(self) -> dict:
        return {
            "arquivo": str(self.arquivo),
            "ok": self.ok,
            "novo": self.novo,
            "antes": self.antes,
            "escritos": self.escritos,
            "mensagem": self.mensagem,
        }


def ler_valores_atuais(exiftool: ExifTool, arquivo: Path, tags: Iterable[str]) -> dict[str, str]:
    [leitura] = exiftool.ler([arquivo], list(tags))
    if not leitura.ok:
        return {}
    return {k: str(v) for k, v in leitura.tags.items() if not k.startswith("ExifTool:")}


def copiar_backup(arquivo: Path, pasta_backup: Path) -> Path:
    """Copia preservando datas; não sobrescreve um backup já existente com o mesmo nome."""
    pasta_backup.mkdir(parents=True, exist_ok=True)
    destino = pasta_backup / arquivo.name
    n = 1
    while destino.exists():
        destino = pasta_backup / f"{arquivo.stem} ({n}){arquivo.suffix}"
        n += 1
    shutil.copy2(arquivo, destino)
    return destino


def pasta_backup_para(arquivo: Path, carimbo: str) -> Path:
    """Backups ficam ao lado das fotos, numa pasta por aplicação."""
    return arquivo.parent / "_backup_ags-media-chrono" / carimbo


def aplicar_data(
    exiftool: ExifTool,
    midia: Midia,
    final: datetime,
    opcoes: OpcoesGravacao | None = None,
    carimbo_backup: str | None = None,
) -> ResultadoAplicacao:
    opcoes = opcoes or OpcoesGravacao()
    arquivo = midia.caminho
    valores = valores_para_gravar(midia, final, opcoes)
    resultado = ResultadoAplicacao(arquivo, ok=False, novo=_data_fuso(final))
    if not valores:
        resultado.mensagem = "Nenhum campo selecionado se aplica a este tipo de arquivo."
        return resultado

    resultado.antes = ler_valores_atuais(exiftool, arquivo, valores)
    if opcoes.backup:
        try:
            copiar_backup(arquivo, pasta_backup_para(arquivo, carimbo_backup or "backup"))
        except OSError as e:
            resultado.mensagem = f"Não foi possível criar o backup: {e}"
            return resultado

    escrita = exiftool.gravar(arquivo, valores)
    if escrita.ok:
        resultado.ok, resultado.escritos = True, list(valores)
        resultado.mensagem = "; ".join(escrita.avisos)
        metadados_pedidos = opcoes.grupos & {
            GrupoCampos.EXIF,
            GrupoCampos.XMP,
            GrupoCampos.QUICKTIME,
        }
        if metadados_pedidos and set(valores) <= set(TAGS_SISTEMA):
            resultado.mensagem = AVISO_SO_ARQUIVO  # ex.: AVI, MKV — sem gravação de metadados
        return resultado

    erro = "; ".join(escrita.erros)
    sistema = {t: v for t, v in valores.items() if t in TAGS_SISTEMA}
    if sistema and any(trecho in erro for trecho in _SEM_SUPORTE):
        # Formato sem suporte a metadados: ao menos as datas do arquivo.
        escrita = exiftool.gravar(arquivo, sistema)
        if escrita.ok:
            resultado.ok, resultado.escritos = True, list(sistema)
            resultado.mensagem = AVISO_SO_ARQUIVO
            return resultado
        erro = "; ".join(escrita.erros)
    resultado.mensagem = erro or "Falha ao gravar"
    return resultado


def aplicar_lote(
    exiftool: ExifTool,
    itens: list[tuple[Midia, datetime]],
    opcoes: OpcoesGravacao | None = None,
    *,
    progresso: Callable[[int, int, Path], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> Operacao:
    """Aplica as datas e salva a operação no histórico (mesmo se cancelada no meio)."""
    operacao = Operacao(TipoOperacao.DATAS)
    for i, (midia, final) in enumerate(itens, start=1):
        if cancelado and cancelado():
            break
        if progresso:
            progresso(i, len(itens), midia.caminho)
        try:
            resultado = aplicar_data(exiftool, midia, final, opcoes, carimbo_backup=operacao.id)
        except Exception as e:  # noqa: BLE001 — um arquivo com problema não para o lote
            resultado = ResultadoAplicacao(midia.caminho, ok=False, mensagem=str(e))
        operacao.entradas.append(resultado.para_entrada())
    if operacao.entradas:
        operacao.salvar()
    return operacao


# --- desfazer -------------------------------------------------------------------------------


def atribuicoes_para_desfazer(entrada: dict) -> list[tuple[str, str]]:
    """Apaga o que foi gravado e restaura os valores antigos (vale a última atribuição)."""
    escritos = entrada.get("escritos", [])
    apagar = [(tag, "") for tag in escritos if tag not in TAGS_SISTEMA]
    restaurar = list(entrada.get("antes", {}).items())
    if not apagar:
        # Só as datas do arquivo foram gravadas (formato sem metadados, ou grupos assim
        # escolhidos): restaurar outros campos falharia ou alteraria o que não foi tocado.
        restaurar = [(tag, valor) for tag, valor in restaurar if tag.startswith("System:")]
    return apagar + restaurar


def desfazer_operacao(
    exiftool: ExifTool,
    operacao: Operacao,
    *,
    progresso: Callable[[int, int, Path], None] | None = None,
) -> list[ResultadoAplicacao]:
    entradas = [e for e in operacao.entradas if e.get("ok")]
    resultados = []
    for i, entrada in enumerate(entradas, start=1):
        arquivo = Path(entrada["arquivo"])
        if progresso:
            progresso(i, len(entradas), arquivo)
        if not arquivo.exists():
            resultados.append(ResultadoAplicacao(arquivo, False, mensagem="Arquivo não encontrado"))
            continue
        escrita = exiftool.gravar_atribuicoes(arquivo, atribuicoes_para_desfazer(entrada))
        resultados.append(
            ResultadoAplicacao(arquivo, escrita.ok, mensagem="; ".join(escrita.erros))
        )
    operacao.desfeita = True
    operacao.salvar()
    return resultados
