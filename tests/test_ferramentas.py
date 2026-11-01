import importlib.util
from pathlib import Path

import pytest

from ags_media_chrono.core import ferramentas
from ags_media_chrono.core.ferramentas import (
    FERRAMENTAS,
    FerramentaNaoEncontrada,
    ferramentas_ausentes,
    localizar,
)

RAIZ = Path(__file__).resolve().parents[1]


def _carregar_script():
    script = RAIZ / "tools" / "baixar_ferramentas.py"
    spec = importlib.util.spec_from_file_location("baixar", script)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _criar(pasta: Path, nome: str) -> Path:
    caminho = pasta / FERRAMENTAS[nome]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.touch()
    return caminho


@pytest.fixture(autouse=True)
def _sem_env(monkeypatch):
    for nome in FERRAMENTAS:
        monkeypatch.delenv(f"AGS_{nome.upper()}", raising=False)


def test_localiza_em_tools_bin(tmp_path):
    esperado = _criar(tmp_path, "exiftool")
    assert localizar("exiftool", pastas_bin=[tmp_path], usar_path=False) == esperado


def test_variavel_de_ambiente_tem_prioridade(tmp_path, monkeypatch):
    _criar(tmp_path / "bin", "ffmpeg")
    outro = tmp_path / "meu_ffmpeg"
    outro.touch()
    monkeypatch.setenv("AGS_FFMPEG", str(outro))
    assert localizar("ffmpeg", pastas_bin=[tmp_path / "bin"], usar_path=False) == outro


def test_usa_path_do_sistema(tmp_path, monkeypatch):
    monkeypatch.setattr(ferramentas.shutil, "which", lambda nome: f"/usr/bin/{nome}")
    assert localizar("exiftool", pastas_bin=[tmp_path]) == Path("/usr/bin/exiftool")


def test_ausente_gera_erro_com_instrucao(tmp_path):
    with pytest.raises(FerramentaNaoEncontrada, match="baixar_ferramentas.py"):
        localizar("ffprobe", pastas_bin=[tmp_path], usar_path=False)


def test_ferramentas_ausentes(tmp_path):
    _criar(tmp_path, "exiftool")
    assert ferramentas_ausentes(pastas_bin=[tmp_path], usar_path=False) == ["ffmpeg", "ffprobe"]


def test_parse_checksums_exiftool():
    script = _carregar_script()
    texto = (
        "SHA2-256(exiftool-13.60_64.zip)= " + "a" * 64 + "\n"
        "SHA1(exiftool-13.60_64.zip)= " + "b" * 40 + "\n"
    )
    assert script.parse_checksums_exiftool(texto) == {"exiftool-13.60_64.zip": "a" * 64}


def test_parse_checksums_sha256sum():
    script = _carregar_script()
    texto = "c" * 64 + "  ffmpeg-n8.1-latest-win64-lgpl-8.1.zip\n"
    assert script.parse_checksums_sha256sum(texto) == {
        "ffmpeg-n8.1-latest-win64-lgpl-8.1.zip": "c" * 64
    }
