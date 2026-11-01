import pytest
from PIL import Image

from ags_media_chrono.core.exiftool import ExifTool, ResultadoEscrita, Saida
from ags_media_chrono.core.ferramentas import FerramentaNaoEncontrada, localizar

try:
    localizar("exiftool")
    TEM_EXIFTOOL = True
except FerramentaNaoEncontrada:
    TEM_EXIFTOOL = False

requer_exiftool = pytest.mark.skipif(not TEM_EXIFTOOL, reason="ExifTool não instalado")


def _jpg(caminho):
    Image.new("RGB", (8, 8), "gray").save(caminho, "JPEG")
    return caminho


@pytest.fixture(scope="module")
def et():
    with ExifTool() as e:
        yield e


# --- testes que não precisam do ExifTool -------------------------------------------------


def test_montar_escrita_sucesso(tmp_path):
    r = ExifTool._montar_escrita(tmp_path / "a.jpg", Saida("    1 image files updated\n", ""))
    assert r == ResultadoEscrita(tmp_path / "a.jpg", ok=True, alterado=True)


def test_montar_escrita_erro(tmp_path):
    saida = Saida(
        "    0 image files updated\n    1 files weren't updated due to errors\n",
        "Error: Not a valid JPG - a.jpg\n",
    )
    r = ExifTool._montar_escrita(tmp_path / "a.jpg", saida)
    assert not r.ok
    assert r.erros == ["Error: Not a valid JPG - a.jpg"]


def test_argumento_com_quebra_de_linha_e_rejeitado(tmp_path):
    e = ExifTool(executavel=tmp_path / "nao-usado")
    with pytest.raises(ValueError):
        e.executar("-Comment=linha1\nlinha2")


# --- integração com o ExifTool real -------------------------------------------------------


@requer_exiftool
def test_versao(et):
    assert et.versao()[0].isdigit()


@requer_exiftool
def test_gravar_e_ler_data(et, tmp_path):
    foto = _jpg(tmp_path / "foto.jpg")
    r = et.gravar(foto, {"EXIF:DateTimeOriginal": "2023:05:12 14:30:00"})
    assert r.ok and r.alterado
    assert not (tmp_path / "foto.jpg_original").exists()

    [lido] = et.ler([foto], ["DateTimeOriginal"])
    assert lido.ok
    assert lido.tags["ExifIFD:DateTimeOriginal"] == "2023:05:12 14:30:00"


@requer_exiftool
def test_gravar_com_backup(et, tmp_path):
    foto = _jpg(tmp_path / "foto.jpg")
    assert et.gravar(foto, {"EXIF:DateTimeOriginal": "2020:01:01 00:00:00"}, backup=True).ok
    assert (tmp_path / "foto.jpg_original").exists()


@requer_exiftool
def test_caminho_com_acentos_e_espacos(et, tmp_path):
    pasta = tmp_path / "Aniversário da Letícia"
    pasta.mkdir()
    foto = _jpg(pasta / "comemoração ç.jpg")
    assert et.gravar(foto, {"EXIF:DateTimeOriginal": "2026:11:01 10:00:00"}).ok
    [lido] = et.ler([foto], ["DateTimeOriginal"])
    assert lido.ok, lido.erro
    assert lido.tags["ExifIFD:DateTimeOriginal"] == "2026:11:01 10:00:00"


@requer_exiftool
def test_erros_por_arquivo_sem_afetar_os_demais(et, tmp_path):
    boa = _jpg(tmp_path / "boa.jpg")
    vazia = tmp_path / "vazia.jpg"
    vazia.touch()
    inexistente = tmp_path / "nao-existe.jpg"
    truncada = tmp_path / "truncada.jpg"
    truncada.write_bytes(b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00garbage")

    r_boa, r_vazia, r_inexistente = et.ler([boa, vazia, inexistente])
    assert r_boa.ok
    assert r_vazia.erro == "File is empty"
    assert r_inexistente.erro.startswith("Error: File not found")

    escrita = et.gravar(truncada, {"EXIF:DateTimeOriginal": "2020:01:01 00:00:00"})
    assert not escrita.ok
    assert escrita.erros[0].startswith("Error: Corrupted JPEG")
    assert et.gravar(boa, {"EXIF:DateTimeOriginal": "2020:01:01 00:00:00"}).ok


@requer_exiftool
def test_muitos_arquivos_com_um_unico_processo(et, tmp_path):
    fotos = [_jpg(tmp_path / f"{i:04d}.jpg") for i in range(300)]
    pid = et.pid
    progresso = []
    resultados = et.ler(fotos, ["FileName"], lote=100, progresso=lambda f, t: progresso.append(f))
    assert len(resultados) == 300 and all(r.ok for r in resultados)
    assert [r.arquivo for r in resultados] == fotos
    assert progresso == [100, 200, 300]
    assert et.pid == pid


@requer_exiftool
def test_gravar_lote_e_cancelar(et, tmp_path):
    fotos = [_jpg(tmp_path / f"{i}.jpg") for i in range(5)]
    itens = [
        (f, {"EXIF:DateTimeOriginal": f"2020:01:0{i + 1} 00:00:00"}) for i, f in enumerate(fotos)
    ]
    contador = {"n": 0}

    def cancelado():
        contador["n"] += 1
        return contador["n"] > 3

    resultados = et.gravar_lote(itens, cancelado=cancelado)
    assert len(resultados) == 3 and all(r.ok for r in resultados)


@requer_exiftool
def test_reinicia_apos_processo_morrer(tmp_path):
    with ExifTool() as e:
        e._processo.kill()
        e._processo.wait()
        assert e.versao()  # executar() reinicia o processo automaticamente
