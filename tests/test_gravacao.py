"""Gravação de datas: leitura -> escrita -> leitura -> desfazer, em amostras de cada origem."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from amostras import criar_amostras, tem

from ags_media_chrono.core.datas import ler_datas
from ags_media_chrono.core.exiftool import ExifTool
from ags_media_chrono.core.gravacao import (
    SUPORTA_DATA_CRIACAO,
    GrupoCampos,
    OpcoesGravacao,
    aplicar_lote,
    atribuicoes_para_desfazer,
    desfazer_operacao,
    valores_para_gravar,
)
from ags_media_chrono.core.historico import TipoOperacao, listar_operacoes
from ags_media_chrono.core.midias import Midia, TipoMidia, listar_midias

BRT = timezone(timedelta(hours=-3))
NOVA = datetime(2024, 2, 29, 15, 45, 30, tzinfo=BRT)

requer_exiftool = pytest.mark.skipif(not tem("exiftool"), reason="ExifTool não instalado")


def _midia(caminho: Path) -> Midia:
    [m] = [x for x in listar_midias(caminho.parent) if x.caminho == caminho]
    return m


def _foto(nome="a.jpg"):
    return Midia(Path(nome), TipoMidia.FOTO, 1, 0)


def _video(nome="a.mp4"):
    return Midia(Path(nome), TipoMidia.VIDEO, 1, 0)


# --- campos a gravar (sem ExifTool) ---------------------------------------------------------


def test_campos_de_foto():
    v = valores_para_gravar(_foto(), NOVA)
    assert v["EXIF:DateTimeOriginal"] == "2024:02:29 15:45:30"
    assert v["EXIF:OffsetTimeOriginal"] == "-03:00"
    assert v["XMP-xmp:CreateDate"] == "2024:02:29 15:45:30-03:00"
    assert v["System:FileModifyDate"] == "2024:02:29 15:45:30-03:00"
    assert ("System:FileCreateDate" in v) == SUPORTA_DATA_CRIACAO
    assert not any(t.startswith("QuickTime") for t in v)


def test_campos_de_video_em_utc():
    v = valores_para_gravar(_video(), NOVA)
    assert v["QuickTime:CreateDate"] == "2024:02:29 18:45:30"  # UTC
    assert v["QuickTime:MediaCreateDate"] == "2024:02:29 18:45:30"
    assert v["Keys:CreationDate"] == "2024:02:29 15:45:30-03:00"
    assert not any(t.startswith(("EXIF", "XMP")) for t in v)
    local = valores_para_gravar(_video(), NOVA, OpcoesGravacao(quicktime_utc=False))
    assert local["QuickTime:CreateDate"] == "2024:02:29 15:45:30"


def test_grupos_desmarcados_e_formatos_sem_metadados():
    so_arquivo = OpcoesGravacao(grupos=frozenset({GrupoCampos.ARQUIVO_MODIFICACAO}))
    assert set(valores_para_gravar(_foto(), NOVA, so_arquivo)) == {"System:FileModifyDate"}
    assert set(valores_para_gravar(_video("a.avi"), NOVA)) <= {
        "System:FileModifyDate", "System:FileCreateDate"
    }  # fmt: skip
    with pytest.raises(ValueError):
        valores_para_gravar(_foto(), NOVA.replace(tzinfo=None))


def test_desfazer_apaga_gravados_e_restaura_antigos():
    entrada = {
        "escritos": ["EXIF:DateTimeOriginal", "XMP-xmp:CreateDate", "System:FileModifyDate"],
        "antes": {"ExifIFD:DateTimeOriginal": "2020:01:01 00:00:00",
                  "System:FileModifyDate": "2020:01:02 00:00:00-03:00"},
    }  # fmt: skip
    assert atribuicoes_para_desfazer(entrada) == [
        ("EXIF:DateTimeOriginal", ""),
        ("XMP-xmp:CreateDate", ""),
        ("ExifIFD:DateTimeOriginal", "2020:01:01 00:00:00"),
        ("System:FileModifyDate", "2020:01:02 00:00:00-03:00"),
    ]
    so_sistema = {"escritos": ["System:FileModifyDate"], "antes": entrada["antes"]}
    assert atribuicoes_para_desfazer(so_sistema) == [
        ("System:FileModifyDate", "2020:01:02 00:00:00-03:00")
    ]


# --- ida e volta com o ExifTool ---------------------------------------------------------------


@pytest.fixture(scope="module")
def et():
    if not tem("exiftool"):
        pytest.skip("ExifTool não instalado")
    with ExifTool() as e:
        yield e


@pytest.fixture
def amostras(tmp_path, et):
    return criar_amostras(tmp_path / "midias", et)


def _retrato(et, arquivo: Path) -> set[tuple[str, str]]:
    """Todas as datas do arquivo (campo + texto), menos as que mudam sozinhas."""
    [d] = ler_datas([arquivo], et)
    return {(c.campo, c.texto) for c in d.candidatas}


@requer_exiftool
@pytest.mark.parametrize(
    "apelido",
    ["iphone_heic", "iphone_jpg", "whatsapp_jpg", "nikon_jpg", "screenshot_png", "iphone_mov",
     "whatsapp_mp4"],
)  # fmt: skip
def test_gravar_ler_e_desfazer(et, amostras, apelido):
    if apelido not in amostras:
        pytest.skip("FFmpeg não instalado")
    arquivo = amostras[apelido]
    antes = _retrato(et, arquivo)

    operacao = aplicar_lote(et, [(_midia(arquivo), NOVA)])
    [entrada] = operacao.entradas
    assert entrada["ok"], entrada["mensagem"]

    [d] = ler_datas([arquivo], et)
    sugerida = d.captura_sugerida()
    if apelido != "screenshot_png" or sugerida is not None:
        assert d.hora_local(sugerida) == NOVA, f"{apelido}: {sugerida}"
    datas_arquivo = {c.campo: d.instante(c) for c in d.candidatas if c.campo.startswith("System")}
    assert datas_arquivo["System:FileModifyDate"] == NOVA
    if SUPORTA_DATA_CRIACAO:
        assert datas_arquivo["System:FileCreateDate"] == NOVA
    # Todas as datas de captura passam a coincidir com a nova
    for c in d.candidatas:
        if c.captura and c.origem.value != "GPS":
            assert d.hora_local(c) == NOVA, c

    desfazer_operacao(et, operacao)
    depois = _retrato(et, arquivo)
    sem_criacao = {x for x in antes if x[0] != "System:FileCreateDate"}
    assert sem_criacao <= depois, sem_criacao - depois
    assert {x for x in depois if x[0] != "System:FileCreateDate"} == sem_criacao


@requer_exiftool
@pytest.mark.parametrize("apelido", ["bmp", "avi"])
def test_formato_sem_metadados_grava_so_datas_do_arquivo(et, amostras, apelido):
    if apelido not in amostras:
        pytest.skip("FFmpeg não instalado")
    arquivo = amostras[apelido]
    original = datetime(2015, 3, 4, 5, 6, 7, tzinfo=BRT)
    os.utime(arquivo, (original.timestamp(), original.timestamp()))

    operacao = aplicar_lote(et, [(_midia(arquivo), NOVA)])
    [entrada] = operacao.entradas
    assert entrada["ok"], entrada["mensagem"]
    assert "só as datas do arquivo" in entrada["mensagem"]
    assert set(entrada["escritos"]) <= {"System:FileModifyDate", "System:FileCreateDate"}
    assert os.stat(arquivo).st_mtime == pytest.approx(NOVA.timestamp())

    [desfeito] = desfazer_operacao(et, operacao)
    assert desfeito.ok, desfeito.mensagem
    assert os.stat(arquivo).st_mtime == pytest.approx(original.timestamp())


@requer_exiftool
def test_backup_e_historico(et, amostras):
    arquivo = amostras["iphone_jpg"]
    original = arquivo.read_bytes()
    operacao = aplicar_lote(et, [(_midia(arquivo), NOVA)], OpcoesGravacao(backup=True))
    copia = arquivo.parent / "_backup_ags-media-chrono" / operacao.id / arquivo.name
    assert copia.read_bytes() == original
    assert arquivo.read_bytes() != original

    [salva] = listar_operacoes(TipoOperacao.DATAS)
    assert salva.id == operacao.id and salva.quantidade_ok == 1 and not salva.desfeita
    desfazer_operacao(et, salva)
    assert listar_operacoes()[0].desfeita


@requer_exiftool
def test_cancelar_no_meio_salva_o_que_foi_feito(et, amostras):
    itens = [(_midia(amostras[k]), NOVA) for k in ("iphone_jpg", "nikon_jpg", "whatsapp_jpg")]
    chamadas = {"n": 0}

    def cancelado():
        chamadas["n"] += 1
        return chamadas["n"] > 2

    operacao = aplicar_lote(et, itens, cancelado=cancelado)
    assert len(operacao.entradas) == 2
    assert listar_operacoes()[0].id == operacao.id


@requer_exiftool
def test_arquivo_inexistente_vira_erro_sem_parar_o_lote(et, amostras, tmp_path):
    fantasma = Midia(tmp_path / "sumiu.jpg", TipoMidia.FOTO, 1, 0)
    operacao = aplicar_lote(et, [(fantasma, NOVA), (_midia(amostras["nikon_jpg"]), NOVA)])
    assert [e["ok"] for e in operacao.entradas] == [False, True]


@pytest.mark.skipif(
    not os.environ.get("AGS_AMOSTRA_NEF"), reason="defina AGS_AMOSTRA_NEF com um .NEF real"
)
@requer_exiftool
def test_nef_real(et, tmp_path):
    """NEF real (não versionado). Ex.: amostra pública da raw.pixls.us."""
    import shutil

    arquivo = tmp_path / "DSC_0202.NEF"
    shutil.copy2(os.environ["AGS_AMOSTRA_NEF"], arquivo)
    antes = _retrato(et, arquivo)
    operacao = aplicar_lote(et, [(_midia(arquivo), NOVA)])
    assert operacao.entradas[0]["ok"], operacao.entradas[0]["mensagem"]
    [d] = ler_datas([arquivo], et)
    assert d.hora_local(d.captura_sugerida()) == NOVA
    desfazer_operacao(et, operacao)
    depois = _retrato(et, arquivo)
    assert {x for x in antes if "FileCreate" not in x[0]} <= depois
